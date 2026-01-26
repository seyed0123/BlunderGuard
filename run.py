from app.server import app
from dotenv import load_dotenv
import os
import subprocess
import atexit

load_dotenv()

LLM_PATH = os.getenv("LLM_path")
if not LLM_PATH:
    raise RuntimeError("LLM_path is not set in .env")

def start_llama_server(llm_path: str, port: int = 8080) -> subprocess.Popen:
    """
    Start llama-server as a subprocess and return the process object.
    The server will be terminated when the Python process exits.
    """
    llama_cmd = [
        "llama-server",
        "-m", llm_path,
        "--port", str(port)
    ]

    print(f"🔥 Starting llama-server on port {port}...")

    proc = subprocess.Popen(
        llama_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    def cleanup():
        print("🛑 Shutting down llama-server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    atexit.register(cleanup)

    return proc


# -----------------------------
# Start llama-server
# -----------------------------
LLAMA_SERVER_PORT = 8080
llama_proc = start_llama_server(LLM_PATH, LLAMA_SERVER_PORT)



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
    )
