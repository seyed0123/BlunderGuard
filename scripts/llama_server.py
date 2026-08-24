"""Start and own a CPU-only local llama-server process."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import requests


def default_cpu_threads() -> int:
    """Use all logical CPUs unless the operating system cannot report them."""
    return os.cpu_count() or 1


def _cpu_max_frequencies(cpu_count: int) -> list[int]:
    """Read Linux CPU frequency tiers, returning no data when unavailable."""
    frequencies = []
    for cpu_index in range(cpu_count):
        frequency_path = Path(
            f"/sys/devices/system/cpu/cpu{cpu_index}/cpufreq/cpuinfo_max_freq"
        )
        try:
            frequencies.append(int(frequency_path.read_text().strip()))
        except (OSError, ValueError):
            return []
    return frequencies


def tuned_cpu_threads(requested_threads: int) -> tuple[int, int]:
    """Tune default thread pools for hybrid CPUs while respecting overrides.

    llama.cpp generation benefits from some efficiency cores on this class of
    CPU, while prompt ingestion is fastest on performance cores alone.  Only
    tune when the caller requested the default (all CPUs) and Linux exposes
    multiple frequency tiers; explicit thread counts and homogeneous CPUs keep
    the requested value for both pools.
    """
    available_threads = default_cpu_threads()
    frequencies = _cpu_max_frequencies(available_threads)
    if requested_threads != available_threads or len(set(frequencies)) < 2:
        return requested_threads, requested_threads

    performance_core_threads = frequencies.count(max(frequencies))
    generation_threads = max(
        performance_core_threads,
        round(available_threads * 0.75),
    )
    return generation_threads, performance_core_threads


@dataclass
class LlamaServerConfig:
    model_path: str | Path
    cpu_server: str | Path
    host: str = "127.0.0.1"
    port: int = 8080
    alias: str = "local-model"
    context_size: int = 4096
    parallel: int = 1
    threads: int = field(default_factory=default_cpu_threads)
    show_output: bool = False
    startup_timeout: float = 600
    health_interval: float = 1
    extra_args: Sequence[str] = field(default_factory=tuple)


class LlamaServer:
    """Own one CPU llama-server process."""

    def __init__(self, config: LlamaServerConfig):
        self.config = config
        self.process: subprocess.Popen | None = None
        self.backend: str | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}/v1"

    def start(self) -> str:
        self._validate_model()
        try:
            print("Starting llama-server with CPU backend...")
            server_path = self._resolve_executable(self.config.cpu_server)
            env = os.environ.copy()
            # A shell configured for OpenVINO must not leak NPU selection into
            # the standalone CPU build.
            env.pop("GGML_OPENVINO_DEVICE", None)
            env.pop("GGML_OPENVINO_PREFILL_CHUNK_SIZE", None)
            output_options = (
                {}
                if self.config.show_output
                else {"stdout": subprocess.DEVNULL, "stderr": subprocess.STDOUT}
            )
            self.process = subprocess.Popen(
                self._command(server_path), env=env, **output_options
            )
            self.wait_until_ready()
        except (FileNotFoundError, OSError, RuntimeError, TimeoutError) as error:
            self.stop()
            raise RuntimeError(f"Could not start CPU llama-server: {error}") from error

        self.backend = "cpu"
        print(f"llama-server is ready on {self.base_url} (CPU).")
        return self.backend

    def _command(self, executable: str | Path) -> list[str]:
        generation_threads, batch_threads = tuned_cpu_threads(self.config.threads)
        return [
            str(executable),
            "--model",
            str(Path(self.config.model_path).expanduser()),
            "--host",
            self.config.host,
            "--port",
            str(self.config.port),
            "--ctx-size",
            str(self.config.context_size),
            "--parallel",
            str(self.config.parallel),
            "--threads",
            str(generation_threads),
            "--threads-batch",
            str(batch_threads),
            "--alias",
            self.config.alias,
            *self.config.extra_args,
        ]

    def wait_until_ready(self) -> None:
        started_at = time.monotonic()
        while time.monotonic() - started_at <= self.config.startup_timeout:
            if self.process is None:
                raise RuntimeError("llama-server process was not created")
            return_code = self.process.poll()
            if return_code is not None:
                raise RuntimeError(f"llama-server exited with return code {return_code}")
            try:
                response = requests.get(
                    f"http://{self.config.host}:{self.config.port}/health",
                    timeout=min(2, self.config.startup_timeout),
                )
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(self.config.health_interval)

        raise TimeoutError(
            f"model did not become ready within {self.config.startup_timeout:g} seconds"
        )

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process = None
        self.backend = None

    def __enter__(self) -> "LlamaServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()

    def _validate_model(self) -> None:
        model_path = Path(self.config.model_path).expanduser()
        if not model_path.is_file():
            raise FileNotFoundError(f"GGUF model not found: {model_path}")

    @staticmethod
    def _resolve_executable(executable: str | Path) -> str:
        requested = str(executable)
        resolved = shutil.which(requested)
        if resolved:
            return resolved
        path = Path(requested).expanduser()
        if path.is_file():
            return str(path)
        raise FileNotFoundError(f"llama-server executable not found: {requested}")
