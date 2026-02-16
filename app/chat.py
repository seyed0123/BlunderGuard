from app.prompt import SINGLE_METHOD,FINAL_CHAIN_METHOD,POSITION_CHAIN_METHOD
from dotenv import load_dotenv
import os
import requests
LLAMA_SERVER_URL = 'http://127.0.0.1:8080/v1/completions'


load_dotenv()

LLM_path = os.getenv('LLM_path')

def build_qwen_chat_prompt(prompt: str) -> str:
    """
    Build Qwen-style chat template (no thinking, single turn).
    Matches tokenizer.apply_chat_template(..., enable_thinking=False)
    """
    return (
        "<|im_start|>user\n"
        f"{prompt}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant"
    )
    
def chat_gguf(prompt: str, max_tokens: int = 128, temperature: float = 0.5, top_p: float = 0.9) -> str:
    full_prompt = build_qwen_chat_prompt(prompt)

    payload = {
        "model": "chess-q4_K_M.gguf",
        "prompt": full_prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p
    }

    try:
        resp = requests.post(LLAMA_SERVER_URL, json=payload, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print("❌ llama-server request failed:", e)
        return ""

    data = resp.json()
    text = data["choices"][0]["text"].strip()

    # Sentence cleanup (same as before)
    for end in [".", "?", "!"]:
        if end in text:
            text = text[: text.rfind(end) + 1]
            break
    else:
        text = text.split("\n")[0].strip()

    return text



def llm_position_analysis(stockfish_text: str,llm_func) -> str:
    prompt = POSITION_CHAIN_METHOD.format(
        analysis=stockfish_text
    )
    return llm_func(prompt)



def llm_move_analysis(before_llm, after_llm, sample, llm_func):
    prompt = FINAL_CHAIN_METHOD.format(
        before_position=before_llm,
        after_position=after_llm,
        position_description_before=sample.get("position_description_before", ""),
        position_description_after=sample.get("position_description_after", ""),
        position_features_white=sample.get("position_features_white", {}),
        position_features_black=sample.get("position_features_black", {}),
        before_stockfish=sample["before"]["stockfish_analysis"],
        after_stockfish=sample["after"]["stockfish_analysis"],
        checkmate_status=sample["checkmate"],
    )
    return llm_func(prompt)


def chain_method(sample,llm_func=chat_gguf):
    # Step 1: LLM evaluates positions independently
    before_llm = llm_position_analysis(sample["before"],llm_func)
    after_llm  = llm_position_analysis(sample["after"],llm_func)

    # Step 2: LLM compares its OWN outputs + Stockfish eval
    final_eval = llm_move_analysis(
        before_llm,
        after_llm,
        sample,
        llm_func
    )

    return final_eval
    
def single_method(sample, llm_func=chat_gguf):
    prompt = SINGLE_METHOD.format(
        position_features_white=sample.get("position_features_white", {}),
        position_features_black=sample.get("position_features_black", {}),
        before_stockfish_analysis=sample["before"],
        after_stockfish_analysis=sample["after"],
        checkmate=sample.get("checkmate", {}),
    )
    
    final_eval = llm_func(prompt)

    return final_eval
