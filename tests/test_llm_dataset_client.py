from types import SimpleNamespace

import pandas as pd

from scripts.llm_dataset_client import ApiCaller


def test_local_openai_compatible_model_is_accepted(monkeypatch):
    requests = []

    class FakeCompletions:
        def create(self, **kwargs):
            requests.append(kwargs)
            message = SimpleNamespace(content="A useful local model response.")
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            assert kwargs == {
                "api_key": "not-needed",
                "base_url": "http://127.0.0.1:8080/v1",
            }
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("scripts.llm_dataset_client.OpenAI", FakeOpenAI)
    caller = ApiCaller(
        api_key="not-needed",
        model="gemma4-12b",
        base_url="http://127.0.0.1:8080/v1",
    )

    result, is_credit_error = caller.api_inference("gemma4-12b", "Judge this")

    assert result == "A useful local model response."
    assert is_credit_error is False
    assert requests[0]["model"] == "gemma4-12b"


def test_existing_prompt_is_used_without_stockfish():
    row = pd.Series({"prompt": "  local prompt  "})

    assert ApiCaller._prompt_for_row(row) == "  local prompt  "
