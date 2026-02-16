import chess.pgn
from tqdm import tqdm
import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv()

from dataset.expert import expert_struct_output,engine
from app.prompt import SINGLE_METHOD

PGN_FILE = "/dataset/lichess_elite_2020-10.pgn"
OUTPUT_FILE = "chess_coach_dataset.csv"

def process_prompt(stockfish_output):
    return SINGLE_METHOD.format(
        position_features_white=stockfish_output.get("position_features_white", {}),
        position_features_black=stockfish_output.get("position_features_black", {}),
        before_stockfish_analysis=stockfish_output["before"],
        after_stockfish_analysis=stockfish_output["after"],
        checkmate=stockfish_output.get("checkmate", {}),
    )

def process_pgn(file_path, max_games=None):
    """Yield parsed games from a PGN file one by one."""
    with open(file_path, encoding="utf-8") as pgn:
        count = 0
        while True:
            game = chess.pgn.read_game(pgn)
            if game is None:
                break
            yield game
            count += 1
            if max_games and count >= max_games:
                break
            
def quick_count_games(file_path):
    count = 0
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('[Event '):
                count += 1
    return count

if __name__ == '__main__':
    try:
        print("📂 Loading PGN games...")
        max_games = 700
        games = process_pgn(PGN_FILE,max_games=max_games)
        total_games = max_games if max_games is not None else quick_count_games(PGN_FILE)
        print(f"✅ Loaded {total_games} games\n")
            
        output_rows = []

        for game_idx, game in enumerate(tqdm(games, desc="Processing games", unit="game", total=total_games)):
            board = game.board()
            moves = list(game.mainline_moves())
            before_fen = board.fen()
            total_moves = len(moves)
            tqdm.write(f"🎯 Game {game_idx+1}/{total_games} — {total_moves} moves")

            
            for move_idx, move in enumerate(tqdm(moves, desc=f"Moves in Game {game_idx+1}", leave=False, unit="move")):
                move_san = board.san(move)
                board.push(move)
                after_fen = board.fen()
                stockfish_output = expert_struct_output(before_fen,after_fen)
                before_fen = after_fen

                prompt = process_prompt(stockfish_output)
                output_rows.append({
                    'before_fen':before_fen,
                    'after_fen':after_fen,
                    'move': move_san,
                    'prompt':prompt,
                    'analyse':'',
                    'analyser':'',
                    'move type':stockfish_output['move_evaluation'],
                })

                if len(output_rows) >= 80:
                    df = pd.DataFrame(output_rows)
                    df.to_csv(OUTPUT_FILE, index=False, mode='a', encoding='utf-8', header=not os.path.exists(OUTPUT_FILE))
                    output_rows = []


            tqdm.write(f"✅ Finished Game {game_idx+1}\n")
    finally:
        engine.quit()