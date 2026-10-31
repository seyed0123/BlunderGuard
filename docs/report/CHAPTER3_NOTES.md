# Persian chapter three and updated report

Outputs:
- `../گزارش پروژه کارشناسی - تکمیل‌شده.pdf`: full report with automatic contents and lists of figures/tables.
- `../گزارش پروژه کارشناسی - تکمیل‌شده.docx`: complete editable report, including references and appendices.
- `../فصل سوم.docx`: standalone chapter three.
- `chapter3_fa.tex`: authoritative editable chapter source.
- `report_updated_fa.tex`: full-report assembly.

The original PDF and Word template remain unchanged. Persian text and headings are typeset using the requested B Nazanin (regular and bold), loaded from `fonts/`. FreeSerif is retained for Latin text and mathematical digits unsupported by the supplied B Nazanin font. This replaces the previous mix of embedded original pages and Amiri chapter-three text. Chapters one and two were transcribed from the supplied PDF, with extraction artifacts corrected, references linked, and the split chapter-two comparison table rebuilt. The original introduction image is preserved as `chapter3_assets/original_intro.png`, extracted losslessly from page 9 of the supplied PDF. References are collected at the end, followed by the data-structure appendix. The second appendix and reference 12 were removed at the user’s request. The title page begins with «به نام خدا» and restores the original Beheshti logo. Letter paper matches the supplied report.

Editable sources: `abstract_fa.tex`, `chapter1_fa.tex`, `chapter2_fa.tex`, `chapter2_table.tex`, `chapter3_fa.tex`, `references_fa.tex`, and `appendices_fa.tex`. `export_word.py` creates the complete Word convenience export using the supplied template and normalizes fonts, table widths and image relationships.

## Evidence

Results come exclusively from `evaluation/judged__model_*.json` at the repository root: 11 models, 60 rows each, judge `gemma4-12b`. Other judge directories are excluded. `chapter3_assets/generate_plots.py` checks the reference keys, score formulas and parse errors, then produces four plots, a CSV, a source manifest and the table rows. Model identities are read from answer_model, not inferred from rank or the repaired filename. Display values use decimal round-half-up to two places.

- Benchmark: `evaluation/evaluation_dataset.tsv` (20 rows in each of `noob`, `intermediate`, `advanced`).
- Dataset grouping: `evaluation/cluster_games.py`.
- Alignment and scoring: `evaluation/judge_responses.py`.
- Implementation: `app/chess/stockfish_analyzer.py`, `app/chess/position_analysis.py`, `app/prompt.py`, `app/chat.py`.
- UI image: existing `software_screenshot.png` (illustrates interface, not evaluation accuracy).
- Position image: copy of `artifacts/evaluation/advanced/g1_m38.png`.
- Flow diagram: authored in TikZ in the chapter; PNG rendering supplied for Word.

The report and slides use only the final `evaluation/judged__model_chess-q8_0_repaired.json` data for Chess Q8. The mean is 2.8583 (displayed 2.86). Superseded results and software-error comparisons are excluded from the scientific discussion. No new training, human evaluation, timing study or causal ablation is claimed.


## Rebuild

From repository root:

```bash
python docs/report/chapter3_assets/generate_plots.py
```

Then run from `docs/report` (XeLaTeX with xepersian, FreeSerif installed, and the B Nazanin files in `fonts/`):

```bash
xelatex report_updated_fa.tex
xelatex report_updated_fa.tex
xelatex report_updated_fa.tex
```

Three passes resolve the contents, page numbers and cross-references. Copy the resulting PDF to the output path above. Word is a convenience export; update the TeX source to reproduce the final PDF. The updated PDF no longer embeds pages from the original PDF.

Final verification: the full Word file was opened with LibreOffice, its automatic contents updated, and all six tables checked to retain their cell text after save. The chapter-two comparison table was visually verified on one page. `normalize_word_tables.py` writes minimal compatible table markup after the template-based export. The PDF remains the authoritative paginated deliverable.

B Nazanin font sources are recorded in `fonts/SOURCES.txt`. The PDF embeds its fonts. Word requires B Nazanin to be available on the machine used for editing. The original introductory illustration remains unchanged.

## Final interpretation

The report abstract, results and conclusion identify the base model as Qwen3-1.7B and compare its 2.86 mean with Llama 3.2 3B (2.86), Gemma 4 26B A4B (2.90) and Gemma 3 12B (2.95). These are similar observed means, not demonstrated statistical equivalence, general capability equivalence or measured computational efficiency. All charts use final results only; there is no before/after comparison. Slides retain English text, Persian timed notes and a 14:15 speaking plan. B Nazanin, the Beheshti logo and the original introduction illustration remain in the report. Persian decimals are explicitly set left-to-right in FreeSerif because the provided B Nazanin lacks U+066B; Persian body text remains B Nazanin.

## User-edited Word revision (19 September 2026)

The Word report was manually edited by the author and is now the authoritative content version. Do not regenerate it from the older TeX sources or run export_word.py over it. This revision replaced only the g1_m38 illustration with artifacts/analysis_images/g1_m38__model_chess-q8_0.png, including the model text. All paragraph text was preserved. The accompanying report PDF is exported from this Word revision.
