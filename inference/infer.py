import subprocess
import sys
import shlex

def run_llama_cli(
    prompt: str,
    model_path: str,
    max_tokens: int = 80,
    temperature: float = 0.35,
    top_p: float = 0.85,
) -> str:
    """
    Call llama.cpp CLI and return the assistant's response.
    """

    llama_cmd = "llama-cli.exe"

    # Qwen chat template
    full_prompt = (
        "<|im_start|>user\n"
        f"{prompt}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant"
    )

    cmd = [
        llama_cmd,
        "-m", model_path,
        "-p", full_prompt,
        "-n", str(max_tokens),
        "--temp", str(temperature),
        "--top-p", str(top_p),
        "--repeat-penalty", "1.15",
        "--reverse-prompt", "<|im_end|>",
        "--no-display-prompt",
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("❌ llama.cpp error:")
        print(e.stderr)
        return ""

    output = result.stdout.strip()

    # Optional cleanup (safety)
    for end in [".", "?", "!"]:
        if end in output:
            output = output[: output.rfind(end) + 1]
            break

    return output.strip()


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    answer = run_llama_cli(
        prompt="Explain why controlling the center is important in chess in 2–3 sentences.",
        model_path="chess-q4_K_M.gguf",
    )

    print("💬 Answer:")
    print(answer)

#  llama-cli -m .\chess-q4_K_M.gguf -p "<|im_start|>user
# >> Explain why controlling the center is important in chess in 2–3 sentences.
# >> <|im_end|>
# >> <|im_start|>assistant" -n 64 --temp 0.35 --top-p 0.9 --repeat-penalty 1.15 --reverse-prompt "<|im_end|>" --no-display-prompt 