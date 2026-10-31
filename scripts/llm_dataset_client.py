import pandas as pd
import time
import random
import logging
import sys,os
from openai import OpenAI
from pathlib import Path

from tqdm import tqdm

from app.chess.board_renderer import analysis_to_png
from app.artifact_naming import (
    MODEL_MARKER,
    dataset_filename,
    model_name_from_dataset,
    validate_model_name,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = PROJECT_ROOT / "artifacts" / "analysis_images"
logger = logging.getLogger(__name__)
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
    def __init__(
        self, api_key: str, model, base_url: str = "https://api.avalai.ir/v1",
        *, llama_cpp: bool = False,
    ):
        """Configure one model; opt into llama.cpp-specific template options."""
        self.api_key = api_key
        self.base_url = base_url
        self.model = validate_model_name(model)
        self.llama_cpp = llama_cpp
        self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

    def api_inference(self, model_name: str, prompt: str) -> tuple[str, bool]:
        """
        Call the configured OpenAI-compatible API for a specific model.
        Returns: (result, is_credit_error)
        """
        try:
            # llama.cpp passes template options through this nested object;
            # the hosted API's top-level flag is ignored by llama.cpp.
            options = (
                {"max_tokens": 512, "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": False}
                }} if self.llama_cpp else {
                    "extra_body": {"enable_thinking": False}
                }
            )
            attempts = 3 if self.llama_cpp else 1
            for attempt in range(1, attempts + 1):
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    **options,
                )
                choice = response.choices[0] if response.choices else None
                message = choice.message if choice else None
                result = getattr(message, "content", None)
                if isinstance(result, str) and len(result.strip()) > 10:
                    return result, False

                # Never use reasoning_content as a substitute for a final answer.
                reason = getattr(choice, "finish_reason", None)
                reasoning = getattr(message, "reasoning_content", None) or ""
                details = (
                    f"finish_reason={reason}, content_chars={len(result or '')}, "
                    f"reasoning_chars={len(reasoning)}, attempts={attempt}"
                )
                logger.warning("Invalid final response from %s: %s", model_name, details)
            return f"ERROR: Empty or invalid response from {model_name} ({details})", False

        except Exception as e:
            error_msg = str(e)
            # Check for credit/quota errors
            if "credit" in error_msg.lower() or "quota" in error_msg.lower():
                return f"CREDIT_ERROR: {model_name} - {error_msg}", True
            elif "rate limit" in error_msg.lower():
                return f"RATE_LIMIT_ERROR: {model_name} - {error_msg}", False
            else:
                return f"ERROR: {model_name} - {error_msg}", False

    @staticmethod
    def _prompt_for_row(row: pd.Series) -> str:
        """Use a source prompt when present, or rebuild it from the position."""
        prompt = row.get("prompt", "")
        if isinstance(prompt, str) and prompt.strip():
            return prompt

        before_fen = row.get("before_fen", "")
        after_fen = row.get("after_fen", "")
        if not before_fen or not after_fen:
            raise ValueError(
                "each input row needs either prompt or before_fen and after_fen"
            )

        # Keep Stockfish initialization out of API-only runs that already have
        # prompts. Prompt-free evaluation files can still be used directly.
        from app.chess.stockfish_analyzer import expert_struct_output
        from scripts.generate_dataset import process_prompt

        return process_prompt(expert_struct_output(before_fen, after_fen))

    def analyse(self, df: pd.DataFrame, target_column: str = 'move type',balancing=True,
                 delay: float = 0.1, output_file: str | Path | None = None) -> pd.DataFrame:
        """
        Optionally balance the dataset and analyze every row with this caller's model.
        Saves results incrementally to CSV.
        EXITS IMMEDIATELY if credit error is encountered.
        """
        if output_file is None:
            output_file = (
                PROJECT_ROOT / "data" / "processed" / dataset_filename(self.model)
            )
        else:
            output_file = Path(output_file)
            if MODEL_MARKER not in output_file.stem:
                output_file = output_file.with_name(
                    dataset_filename(self.model, output_file.stem)
                )
            elif model_name_from_dataset(output_file) != self.model:
                raise ValueError(
                    "output filename model must match ApiCaller model: "
                    f"{output_file.name!r} vs {self.model!r}"
                )
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if balancing:
            balanced = balancer(df, target_column=target_column)
        else:
            balanced = df

        # Prepare output list - will have 2 rows per original row
        output_rows = []

        # Track progress
        total_rows = len(balanced)
        print(f"Processing {total_rows} original rows")

        for idx, row in tqdm(
                balanced.iterrows(),
                total=len(balanced),
                desc="Processing rows"
        ):

            if idx%20==0:
                self._save_progress(output_rows, output_file)

            # Extract common data from the row
            row_id = row.get('row_id', str(idx))
            before_fen = row.get('before_fen', '')
            after_fen = row.get('after_fen', '')
            move_san = row.get('move', '')
            prompt = self._prompt_for_row(row)
            move_type = row.get('move type', '')
            move_evaluation = row.get('move evaluation', '')
            type = row.get('type')

            # Call first model
            result_1, is_credit_error_1 = self.api_inference(self.model, prompt)
            is_success_1 = not result_1.startswith("ERROR:") and not result_1.startswith("CREDIT_ERROR:")


            row_1 = {
                'row_id': row_id,
                'before_fen': before_fen,
                'after_fen': after_fen,
                'move': move_san,
                'analyse': result_1,
                'analyser': self.model,
                'move type': move_type,
                'move evaluation': move_evaluation,
                'type': type,
            }
            output_rows.append(row_1.copy())
            img_path = os.path.join(IMG_DIR, f"{row_id}__model_{self.model}.png")
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

    def _save_progress(self, output_rows: list, output_file: str | Path):
        """Save current progress to CSV file."""
        try:
            df_temp = pd.DataFrame(output_rows)
            df_temp.to_csv(output_file, index=False, encoding='utf-8-sig')
        except Exception as e:
            print(f"Warning: Could not save progress: {e}")
