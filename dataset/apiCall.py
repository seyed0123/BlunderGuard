import pandas as pd
import time
from typing import Optional


def balancer(df: pd.DataFrame, target_column: str = 'move type', random_state: int = 42) -> pd.DataFrame:
    """Balance dataset by undersampling majority classes."""
    class_counts = df[target_column].value_counts()
    min_count = class_counts.min()

    balanced_df = df.groupby(target_column, group_keys=False).apply(
        lambda x: x.sample(n=min_count, random_state=random_state)
    )

    balanced_df = balanced_df.sample(frac=1, random_state=random_state).reset_index(drop=True)
    return balanced_df


class ApiCaller:
    def __init__(self, model_name: str, url: str, token_header: str, token: str):
        self.model_name = model_name
        self.url = url
        self.token_header = token_header
        self.token = token

    def api_inference(self, prompt: str) -> Optional[str]:
        """Call API and return response. Implement actual logic here."""
        # Example placeholder:
        # response = requests.post(...)
        # return response.json()['result']
        pass

    def analyser(self, df: pd.DataFrame, target_column: str = 'move type',
                 delay: float = 0.1) -> pd.DataFrame:
        """Balance dataset and analyze each row with API inference."""
        balanced = balancer(df, target_column=target_column)
        balanced['analyser'] = self.model_name


        for idx, row in balanced.iterrows():
            try:
                result = self.api_inference(row['prompt'])
                balanced.at[idx, 'analyse'] = result
            except Exception as e:
                balanced.at[idx, 'analyse'] = f"ERROR: {str(e)}"

            # Rate limiting to avoid API throttling
            if delay > 0:
                time.sleep(delay)

        return balanced