"""Rebuild report plots and table from the 11 saved Gemma judge files."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import csv
import json
import os
import tempfile
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'blunderguard-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
METRICS = ['correctness', 'instruction_following', 'helpfulness', 'faithfulness', 'fluency', 'overall']
NAMES = {'Llama-3.2-3B-Instruct-Q4_K_M': 'Llama 3.2 3B (Q4)', 'cf.gemma-4-26b-a4b-it': 'Gemma 4 26B A4B', 'cf.llama-3.3-70b-instruct-fp8-fast': 'Llama 3.3 70B (FP8)', 'chess-q8_0': 'Chess Q8 (Qwen3 1.7B)', 'gemini-3.5-flash': 'Gemini 3.5 Flash', 'gemma-3-12b-it-Q4_0': 'Gemma 3 12B (Q4)', 'gpt-5.5': 'GPT-5.5', 'gpt-oss-120b': 'GPT-OSS 120B', 'grok-4.3': 'Grok 4.3', 'qwen3-30b-a3b': 'Qwen3 30B A3B', 'qwen3.7-plus': 'Qwen3.7 Plus'}
def mean(rows, metric):
    return sum(Decimal(str(r['scores'][metric])) for r in rows) / len(rows)
def fmt(value):
    return str(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
paths = sorted((ROOT / 'evaluation').glob('judged__model_*.json'))
repaired = ROOT / 'evaluation/judged__model_chess-q8_0_repaired.json'
assert repaired.is_file(), 'The repaired Chess Q8 results are required.'
paths = [p for p in paths if p.name != 'judged__model_chess-q8_0.json']
data = [json.loads(p.read_text()) for p in paths]
assert len({d['answer_model'] for d in data}) == len(data)
(OUT / 'results_sources.json').write_text(json.dumps(
    {d['answer_model']: str(p.relative_to(ROOT)) for p, d in zip(paths, data)}, indent=2))
assert len(data) == 11
with (ROOT / 'evaluation/evaluation_dataset.tsv').open() as f:
    reference_keys = {(r['type'], r['row_id']) for r in csv.DictReader(f, delimiter='\t')}
for d in data:
    assert d['judge_model'] == 'gemma4-12b' and len(d['results']) == 60
    assert {(r['type'], r['row_id']) for r in d['results']} == reference_keys
    for r in d['results']:
        s = r['scores']
        assert not s.get('parse_error')
        weighted = sum(Decimal(str(s[m])) * w for m, w in zip(METRICS[:5], map(Decimal, ['.35','.1','.2','.25','.1'])))
        assert abs(weighted - Decimal(str(s['overall']))) <= Decimal('.01')
    d['means'] = {m: mean(d['results'], m) for m in METRICS}
data.sort(key=lambda d: d['means']['overall'], reverse=True)
plt.rcParams.update({'font.size':11, 'font.family':'FreeSerif', 'axes.spines.top':False, 'axes.spines.right':False, 'savefig.dpi':200})
y = np.arange(len(data)); labels = [NAMES[d['answer_model']] for d in data]
fig, ax = plt.subplots(figsize=(9,5.2), layout='constrained')
vals = [float(d['means']['overall']) for d in data]
ax.barh(y, vals, color=['#b75b35' if d['answer_model']=='chess-q8_0' else '#276678' for d in data])
ax.set_yticks(y, labels); ax.invert_yaxis(); ax.set_xlim(0,10)
ax.set_xlabel('Mean weighted overall score (0–10)'); ax.xaxis.grid(True,alpha=.15); ax.set_axisbelow(True)
for i,v in enumerate(vals): ax.text(v+.08,i,fmt(data[i]['means']['overall']),va='center',fontsize=10)
fig.savefig(OUT/'overall.png'); plt.close(fig)
for filename, cols, matrix in [
    ('metrics.png', ['Correctness','Instruction\nfollowing','Helpfulness','Faithfulness','Fluency'], [[d['means'][m] for m in METRICS[:5]] for d in data]),
    ('categories.png', ['Beginner (n=20)','Intermediate (n=20)','Advanced (n=20)'], [[mean([r for r in d['results'] if r['type']==c], 'overall') for c in ['noob','intermediate','advanced']] for d in data])]:
    fig, ax = plt.subplots(figsize=(9,5.3), layout='constrained')
    im=ax.imshow(np.array(matrix,dtype=float),vmin=0,vmax=10,cmap='YlGnBu',aspect='auto')
    ax.set_yticks(y,labels); ax.set_xticks(range(len(cols)),cols)
    for i,row in enumerate(matrix):
        for j,v in enumerate(row): ax.text(j,i,fmt(v),ha='center',va='center',color='white' if v>6 else '#17252a',fontsize=9)
    fig.colorbar(im,ax=ax,label='Mean score (0–10)'); fig.savefig(OUT/filename); plt.close(fig)
with (OUT/'verified_results.csv').open('w') as f:
    w=csv.writer(f); w.writerow(['model','n']+METRICS)
    w.writerows([[d['answer_model'],60]+[d['means'][m] for m in METRICS] for d in data])
rows=[]
for d in data:
    cells=[NAMES[d['answer_model']].replace('_',r'\_')]+[fmt(d['means'][m]) for m in ['correctness','faithfulness','helpfulness','overall']]
    rows.append(' & '.join(r'\lr{'+c+'}' for c in cells)+r' \\')
(OUT/'results_rows.tex').write_text('\n'.join(rows)+'\n')
print('Verified 660 judgments; rebuilt three plots and the results table.')

category_rows = []
for d in data:
    cells = [NAMES[d['answer_model']].replace('_', r'\_')] + [fmt(mean([r for r in d['results'] if r['type'] == c], 'overall')) for c in ['noob', 'intermediate', 'advanced']]
    category_rows.append(' & '.join(r'\lr{' + c + '}' for c in cells) + r' \\')
(OUT / 'category_rows.tex').write_text('\n'.join(category_rows) + '\n')

# Compare final observed means for the small model and selected larger models.
fig, ax = plt.subplots(figsize=(9, 4), layout='constrained')
models = ['chess-q8_0','Llama-3.2-3B-Instruct-Q4_K_M','cf.gemma-4-26b-a4b-it','gemma-3-12b-it-Q4_0']
values = [next(d['means']['overall'] for d in data if d['answer_model']==m) for m in models]
ax.barh(range(4),[float(v) for v in values],color=['#b75b35','#276678','#276678','#276678'])
ax.set_yticks(range(4),['Chess Q8 — Qwen3 1.7B','Llama 3.2 — 3B','Gemma 4 — 26B A4B','Gemma 3 — 12B'])
ax.invert_yaxis();ax.set_xlim(0,10);ax.set_xlabel('Mean overall score (0–10)')
ax.set_title('Similar scores to selected larger models')
for i,v in enumerate(values): ax.text(float(v)+.1,i,fmt(v),va='center')
fig.savefig(OUT/'small_model_comparison.png');plt.close(fig)
