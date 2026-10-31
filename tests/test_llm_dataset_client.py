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


def make_caller(monkeypatch, responses, **options):
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        return responses.pop(0)

    monkeypatch.setattr(
        'scripts.llm_dataset_client.OpenAI',
        lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create))),
    )
    return ApiCaller('not-needed', 'chess-q8_0', **options), requests


def completion(content, reasoning=None, finish='stop'):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, reasoning_content=reasoning),
        finish_reason=finish)])


def test_llama_cpp_disables_thinking_in_chat_template(monkeypatch):
    caller, requests = make_caller(monkeypatch, [completion('A final explanation.')],
                                    llama_cpp=True)
    assert caller.api_inference('chess-q8_0', 'Explain this')[0] == 'A final explanation.'
    assert requests[0]['extra_body'] == {'chat_template_kwargs': {'enable_thinking': False}}
    assert requests[0]['max_tokens'] == 512


def test_hosted_api_keeps_its_existing_thinking_option(monkeypatch):
    caller, requests = make_caller(monkeypatch, [completion('A final explanation.')])
    caller.api_inference('chess-q8_0', 'Explain this')
    assert requests[0]['extra_body'] == {'enable_thinking': False}
    assert 'max_tokens' not in requests[0]


def test_empty_local_answer_is_retried_without_using_reasoning(monkeypatch):
    caller, requests = make_caller(monkeypatch, [
        completion('', 'Unfinished internal reasoning', 'length'),
        completion('A final explanation.'),
    ], llama_cpp=True)
    result, credit = caller.api_inference('chess-q8_0', 'Explain this')
    assert result == 'A final explanation.'
    assert not credit
    assert len(requests) == 2


def test_persistent_empty_answer_has_bounded_retries_and_diagnostics(monkeypatch):
    caller, requests = make_caller(monkeypatch, [
        completion(None, 'Internal reasoning', 'length') for _ in range(3)
    ], llama_cpp=True)
    result, credit = caller.api_inference('chess-q8_0', 'Explain this')
    assert result.startswith('ERROR:')
    assert 'finish_reason=length' in result
    assert 'reasoning_chars=18' in result
    assert 'Internal reasoning' not in result
    assert len(requests) == 3
    assert not credit
