import pandas as pd
import time
import random
import sys,os
from openai import OpenAI
from pathlib import Path

from tqdm import tqdm

from app.chess.board_renderer import analysis_to_png

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = PROJECT_ROOT / "artifacts" / "analysis_images"
MODELS = ['qwen3.7-plus', "gemini-3.5-flash", "grok-4.3", "gpt-5.5", "deepseek-v4-flash"]


def balancer(df: pd.DataFrame, target_column: str = 'move type', random_state: int = 42) -> pd.DataFrame:
    """Balance dataset by undersampling majority classes."""
    excluded_types = ['Good', 'Great']
    filtered_df = df[~df[target_column].isin(excluded_types)]

    class_counts = filtered_df[target_column].value_counts()
    min_count = class_counts.min()

    balanced_df = filtered_df.groupby(target_column, group_keys=False).apply(
        lambda x: x.sample(n=min_count, random_state=random_state)
    )

    balanced_df = balanced_df.sample(frac=1, random_state=random_state).reset_index(drop=True)
    return balanced_df


class ApiCaller:
    def __init__(self, api_key: str,model, base_url: str = "https://api.avalai.ir/v1"):
        """
        api_keys: dict mapping model names to their API keys
        Example: {'qwen3.7-plus': 'key1', 'gemini-3.5-flash': 'key2'}
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

    def api_inference(self, model_name: str, prompt: str) -> tuple[str, bool]:
        """
        Call AvalAI OpenAI-compatible chat API for a specific model.
        Returns: (result, is_credit_error)
        """
        if model_name not in MODELS:
            return f"ERROR: Model {model_name} not configured", False

        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            )

            result = response.choices[0].message.content

            # Check if result looks valid (not empty or error-like)
            if result and len(result.strip()) > 10:
                return result, False
            else:
                return f"ERROR: Empty or invalid response from {model_name}", False

        except Exception as e:
            error_msg = str(e)
            # Check for credit/quota errors
            if "credit" in error_msg.lower() or "quota" in error_msg.lower():
                return f"CREDIT_ERROR: {model_name} - {error_msg}", True
            elif "rate limit" in error_msg.lower():
                return f"RATE_LIMIT_ERROR: {model_name} - {error_msg}", False
            else:
                return f"ERROR: {model_name} - {error_msg}", False

    def analyse(self, df: pd.DataFrame, target_column: str = 'move type',balancing=True,
                 delay: float = 0.1,
                 output_file: str = str(PROJECT_ROOT / "data" / "processed" / "chess_coach_dataset_complete.csv")) -> pd.DataFrame:
        """
        Balance dataset and analyze each row with 2 randomly selected models.
        Creates TWO separate rows per original row (one for each model).
        Saves results incrementally to CSV.
        EXITS IMMEDIATELY if credit error is encountered.
        """
        if balancing:
            balanced = balancer(df, target_column=target_column)
        else:
            balanced = df

        # Prepare output list - will have 2 rows per original row
        output_rows = []

        # Track progress
        total_rows = len(balanced)
        print(f"Processing {total_rows} original rows")

        for idx, row in tqdm(balanced.iterrows()):

            if idx%20==0:
                self._save_progress(output_rows, output_file)

            # Extract common data from the row
            row_id = row.get('row_id', str(idx))
            before_fen = row.get('before_fen', '')
            after_fen = row.get('after_fen', '')
            move_san = row.get('move', '')
            prompt = row['prompt']
            move_type = row.get('move type', '')
            move_evaluation = row.get('move evaluation', '')
            type = row.get('type')

            # Call first model
            result_1, is_credit_error_1 = self.api_inference(self.model, prompt)
            is_success_1 = not result_1.startswith("ERROR:") and not result_1.startswith("CREDIT_ERROR:")


            row_1 = {
                'id': row_id,
                'before_fen': before_fen,
                'after_fen': after_fen,
                'move': move_san,
                'prompt': prompt,
                'analyse': result_1,
                'analyser': self.model,
                'move type': move_type,
                'move evaluation': move_evaluation,
                'type': type,
                'status': "SUCCESS" if is_success_1 else "FAILED"
            }
            output_rows.append(row_1.copy())
            img_path = os.path.join(IMG_DIR, row_id+self.model + ".png")
            row_1['before']={'fen':before_fen}
            row_1['after'] = {'fen': after_fen}
            row_1['played_move'] = move_san
            row_1['move_evaluation']=move_evaluation
            analysis_to_png(row_1, result_1, img_path)

            if is_credit_error_1:

                self._save_progress(output_rows, output_file)

                print("✅ Data saved successfully.")
                print("❌ Exiting application due to insufficient credits.")
                print("=" * 60)

                # Save final CSV
                df_temp = pd.DataFrame(output_rows)
                df_temp.to_csv(output_file, index=False, encoding='utf-8-sig')

                # Exit the program
                sys.exit(1)

            # Save progress after each original row (2 result rows)
            self._save_progress(output_rows, output_file)

            # Rate limiting
            if delay > 0:
                time.sleep(delay)

        print(f"\n✅ Completed! Results saved to {output_file}")
        print(f"Total result rows: {len(output_rows)}")

        # Return as DataFrame
        return pd.DataFrame(output_rows)

    def _save_progress(self, output_rows: list, output_file: str):
        """Save current progress to CSV file."""
        try:
            df_temp = pd.DataFrame(output_rows)
            df_temp.to_csv(output_file, index=False, encoding='utf-8-sig')
        except Exception as e:
            print(f"Warning: Could not save progress: {e}")
