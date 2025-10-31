import chess.pgn
from tqdm import tqdm
import pandas as pd
from expert import get_best_moves,engine
import os

PGN_FILE = "dataset\lichess_elite_2023-10.pgn"
OUTPUT_FILE = "chess_coach_dataset.csv"

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
        games = process_pgn(PGN_FILE,max_games=20)
        total_games = quick_count_games(PGN_FILE)
        print(f"✅ Loaded {total_games} games\n")
            
        output_rows = []

        for game_idx, game in enumerate(tqdm(games, desc="Processing games", unit="game", total=total_games)):
            board = game.board()
            before_prompt,before_player,before_best = None,None,None
            
            moves = list(game.mainline_moves())
            total_moves = len(moves)
            tqdm.write(f"🎯 Game {game_idx+1}/{total_games} — {total_moves} moves")

            
            for move_idx, move in enumerate(tqdm(moves, desc=f"Moves in Game {game_idx+1}", leave=False, unit="move")):
                move_san = board.san(move)
                board.push(move)
                after_prompt,after_player,after_best = get_best_moves(board)


                if before_prompt is not None:

                    output_rows.append({
                        'before_prompt': before_prompt,
                        'after_prompt': after_prompt,
                        'move': move_san,
                        'after_player':after_player,
                        'after_win_proba':after_best,
                        'before_player':before_player,
                        'before_win_proba':before_best,
                        'commentary': ""
                    })

                before_prompt,before_player,before_best = after_prompt,after_player,after_best 
                if len(output_rows) >= 1000:
                    df = pd.DataFrame(output_rows)
                    df.to_csv(OUTPUT_FILE, index=False, mode='a', encoding='utf-8', header=not os.path.exists(OUTPUT_FILE))
                    output_rows = []
                    print(f"✅ Done! Saved {len(df)} entries to 'chess_coach_dataset.csv'")


            tqdm.write(f"✅ Finished Game {game_idx+1}\n")

        # Save results
        # print(f"💾 Saving {len(output_rows)} entries to 'chess_coach_dataset.csv'...")
        # df = pd.DataFrame(output_rows)
        # df.to_csv('chess_coach_dataset.csv', index=False, encoding='utf-8')

        # print(f"✅ Done! Saved {len(df)} entries to 'chess_coach_dataset.csv'")
    finally:
        engine.quit()