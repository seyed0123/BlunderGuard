import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from app.artifact_naming import model_name_from_gguf
from scripts.llm_dataset_client import ApiCaller
from scripts.llama_server import LlamaServer, LlamaServerConfig, default_cpu_threads


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Generate candidate analyses through an OpenAI-compatible API."
    )
    parser.add_argument(
        "--input",
        default=str(PROJECT_ROOT / "evaluation" / "evaluation_dataset.tsv"),
    )
    parser.add_argument("--model", default=os.getenv("MODEL", "local-model"))
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENAI_BASE_URL", "https://api.avalai.ir/v1"),
        help="Hosted API URL or llama-server URL, e.g. http://localhost:8080/v1",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY") or "not-needed",
    )
    parser.add_argument("--output", default=None)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--balance", action="store_true")
    parser.add_argument(
        "--llama-cpp", action="store_true",
        help="use llama.cpp chat-template options for an already-running server",
    )
    parser.add_argument(
        "--gguf",
        help="start a local llama-server for this GGUF before inference",
    )
    parser.add_argument(
        "--cpu-server",
        default=os.getenv("LLAMA_CPU_SERVER", "llama-server"),
        help="CPU llama-server executable",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--context-size", type=int, default=4096)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--threads", type=int, default=default_cpu_threads())
    parser.add_argument(
        "--show-server-output",
        action="store_true",
        help="show llama-server logs (hidden by default)",
    )
    parser.add_argument("--startup-timeout", type=float, default=600)
    args = parser.parse_args()

    dataframe = pd.read_csv(args.input, sep="\t")
    server = None
    base_url = args.base_url
    if args.gguf:
        # A managed local model is named from its actual artifact so its alias,
        # CSV filename, and later evaluation metadata cannot drift apart.
        args.model = model_name_from_gguf(args.gguf)
        server = LlamaServer(
            LlamaServerConfig(
                model_path=args.gguf,
                cpu_server=args.cpu_server,
                host=args.host,
                port=args.port,
                alias=args.model,
                context_size=args.context_size,
                parallel=args.parallel,
                threads=args.threads,
                show_output=args.show_server_output,
                startup_timeout=args.startup_timeout,
            )
        )
        server.start()
        base_url = server.base_url

    try:
        caller = ApiCaller(
            api_key=args.api_key,
            model=args.model,
            base_url=base_url,
            llama_cpp=bool(args.gguf) or args.llama_cpp,
        )
        caller.analyse(
            dataframe,
            balancing=args.balance,
            delay=args.delay,
            output_file=args.output,
        )
    finally:
        if server is not None:
            server.stop()


if __name__ == "__main__":
    main()
