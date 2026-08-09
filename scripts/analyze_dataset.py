import pandas as pd

from pathlib import Path
import os

from scripts.llm_dataset_client import ApiCaller
from dotenv import load_dotenv
load_dotenv()
model = 'qwen3.7-plus'
api_key = os.getenv("API_KEY")
caller = ApiCaller(api_key=api_key,model=model)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(PROJECT_ROOT / "evaluation" / f"evaluation_dataset.tsv",sep="\t")
caller.analyse(df,balancing=False)
