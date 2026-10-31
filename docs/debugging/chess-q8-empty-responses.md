# Chess Q8 empty responses: diagnosis and repair

Six saved candidates contained `ERROR: Empty or invalid response from chess-q8_0`:

- advanced / g2_m44
- advanced / g3_m26
- noob / g4_m5
- intermediate / g1_m42
- intermediate / g4_m36
- intermediate / g9_m33

## Cause and reproduction

The dataset client sent `enable_thinking: false` at the top level. That is the
existing hosted API option, but llama.cpp expects this option inside
`chat_template_kwargs`. The local server therefore did not disable Qwen3's
thinking template. A response can have reasoning text but no final `content`;
the client only accepts final content and saved its generic error message.

A controlled reproduction used the original prompt for advanced/g2_m44, the
local chess-q8_0.gguf artifact, llama-b9536, seed 42, and a 512-token output
limit. The old request returned an empty final answer, nonempty reasoning, and
`finish_reason: length` after 512 generated tokens. The corrected request
returned a final answer with `finish_reason: stop` after 87 tokens. The server's
`/apply-template` output also confirmed the change in template. This reproduces
the failure mechanism; the historical run did not retain raw responses, so its
exact token counts and finish reasons cannot be recovered for all six errors.

The installed llama.cpp documentation describes `chat_template_kwargs` in
`/home/seyed/npu/llama.cpp/tools/server/README.md`. Raw reproduction requests,
responses and templates are in `artifacts/chess_q8_repair/`.

## Fix

- Managed `scripts.analyze_dataset --gguf ...` runs now pass the correct nested
  template option automatically.
- For an existing llama-server, use `--llama-cpp --base-url ...`.
- Hosted API requests keep their existing option.
- Local generation has a 512-token output budget and at most three attempts for
  empty/too-short final responses. Persistent errors include finish reason and
  content/reasoning lengths. Reasoning is never treated as a final explanation.

## Repaired data

`data/processed/repaired/chess_coach_dataset_complete__model_chess-q8_0.csv`
contains all 60 rows, with only the six error responses replaced. All six
returned complete final answers on their first attempt. The 54 valid original
responses and every row's metadata were checked for equality against the
original. Original CSV and judgment files remain unchanged.

Requests and raw generated responses are saved in
`artifacts/chess_q8_repair/regeneration.json`. Reproduction, regeneration and
rejudging scripts are saved beside that evidence. The repaired dataset is a
partial rerun with corrected inference settings, not a fresh controlled run of
all 60 positions. Filling missing answers does not establish chess correctness.

## Verification

The regression tests cover the llama.cpp option, preserving hosted settings,
retrying empty final content without exposing reasoning, and bounded failure
with diagnostics. The test run passed 29 tests. Three existing integration
tests require the Flask service at localhost:8000 and failed because network
access was unavailable in the sandbox; they did not exercise this dataset fix.
The six real-model generations provide a separate end-to-end check.

## Re-scored results

`evaluation/repaired/judged__model_chess-q8_0.json` contains the repaired
60-row evaluation. Only the six replacement responses were scored again,
using the existing Gemma4-12B judge, rubric and scoring function; all other
54 judgments are unchanged. The resulting mean weighted score is **2.8583/10**
(previously **2.4942/10**). This partial repair should be identified as such if
used in an updated report or presentation. Existing report and slide scores
continue to describe the original saved experiment.

| Group | Row | Replacement score / 10 |
|---|---|---:|
| advanced | g2_m44 | 2.40 |
| advanced | g3_m26 | 1.90 |
| noob | g4_m5 | 6.65 |
| intermediate | g1_m42 | 2.00 |
| intermediate | g4_m36 | 5.25 |
| intermediate | g9_m33 | 3.65 |
