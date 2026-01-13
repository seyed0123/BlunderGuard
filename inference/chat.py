from prompt import SINGLE_MDETHOD,FINAL_CHAIN_METHOD,POSITION_CHAIN_METHOD
from dotenv import load_dotenv
import os

load_dotenv()

LLM_path = os.getenv('LLM_path')
def chat_gguf(prompt: str, max_tokens: int = 64) -> str:
    """
    Qwen-style GGUF chat, faithful to llama-cli usage
    """
    raise NotImplementedError('pls implement the qwen chat using lama cpp')



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
    prompt = SINGLE_MDETHOD.format(
        position_description_before=sample.get("position_description_before", ""),
        position_description_after=sample.get("position_description_after", ""),
        position_features_white=sample.get("position_features_white", {}),
        position_features_black=sample.get("position_features_black", {}),
        before_stockfish_analysis=sample["before"]["stockfish_analysis"],
        after_stockfish_analysis=sample["after"]["stockfish_analysis"],
        checkmate=sample.get("checkmate", {}),
    )
    
    final_eval = llm_func(prompt)

    return final_eval
