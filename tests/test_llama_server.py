from types import SimpleNamespace

import pytest

from scripts.llama_server import LlamaServer, LlamaServerConfig, default_cpu_threads


class FakeProcess:
    def __init__(self, return_code=None):
        self.return_code = return_code
        self.terminated = False

    def poll(self):
        return self.return_code

    def terminate(self):
        self.terminated = True
        self.return_code = 0

    def wait(self, timeout=None):
        return self.return_code

    def kill(self):
        self.return_code = -9


def config(tmp_path):
    model = tmp_path / "model.gguf"
    model.touch()
    cpu = tmp_path / "llama-server-cpu"
    cpu.touch(mode=0o755)
    return LlamaServerConfig(
        model_path=model,
        cpu_server=cpu,
        startup_timeout=1,
    )


def test_default_threads_uses_every_available_cpu(monkeypatch):
    monkeypatch.setattr("scripts.llama_server.os.cpu_count", lambda: 16)

    assert default_cpu_threads() == 16


def test_starts_only_cpu_and_removes_openvino_environment(monkeypatch, tmp_path):
    launches = []

    def fake_popen(command, **kwargs):
        launches.append((command, kwargs))
        return FakeProcess()

    monkeypatch.setattr("scripts.llama_server.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "scripts.llama_server.requests.get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200),
    )

    server = LlamaServer(config(tmp_path))
    monkeypatch.setenv("GGML_OPENVINO_DEVICE", "NPU")
    monkeypatch.setenv("GGML_OPENVINO_PREFILL_CHUNK_SIZE", "256")

    assert server.start() == "cpu"
    assert len(launches) == 1
    assert launches[0][0][0].endswith("llama-server-cpu")
    assert launches[0][1]["stdout"] is __import__("subprocess").DEVNULL
    assert launches[0][1]["stderr"] is __import__("subprocess").STDOUT
    assert "GGML_OPENVINO_DEVICE" not in launches[0][1]["env"]
    assert "GGML_OPENVINO_PREFILL_CHUNK_SIZE" not in launches[0][1]["env"]


def test_reports_cpu_startup_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "scripts.llama_server.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(return_code=1),
    )

    with pytest.raises(RuntimeError, match="CPU"):
        LlamaServer(config(tmp_path)).start()


def test_command_contains_model_alias_and_network_options(tmp_path):
    server_config = config(tmp_path)
    server_config.host = "127.0.0.1"
    server_config.port = 9090
    server_config.alias = "gemma4-12b"
    server_config.threads = 12

    command = LlamaServer(server_config)._command(server_config.cpu_server)

    assert command[command.index("--model") + 1].endswith("model.gguf")
    assert command[command.index("--alias") + 1] == "gemma4-12b"
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "9090"
    assert command[command.index("--threads") + 1] == "12"
    assert command[command.index("--threads-batch") + 1] == "12"


def test_default_context_is_large_enough_for_dataset_prompts(tmp_path):
    server_config = config(tmp_path)
    server_config.context_size = LlamaServerConfig(
        model_path=server_config.model_path,
        cpu_server=server_config.cpu_server,
    ).context_size

    command = LlamaServer(server_config)._command(server_config.cpu_server)

    assert int(command[command.index("--ctx-size") + 1]) >= 4096
