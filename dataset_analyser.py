import pandas as pd

from dataset.apiCall import ApiCaller
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("API_KEY")
caller = ApiCaller(api_key=api_key)

df = pd.read_csv('chess_coach_dataset.csv')
caller.analyse(df,)