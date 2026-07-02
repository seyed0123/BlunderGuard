import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
import chess.pgn
import pandas as pd
from tqdm import tqdm

from dataset.board_widget import analysis_to_png
from dataset.expert import expert_struct_output, engine
from dataset_maker import process_prompt
from game_clusterer import OUTPUTS

selected_moves = {
    'noob' : [
        (0,12,1),
        (0,22,0),
        (1,6,0),
        (1,8,1),
        (1,22,2),
        (2,11,0),
        (2,17,0),
        (3,17,0),
        (3,42,0),
        (4,3,1),
        (4,10,0),
        (4,17,0),
        (5,31,1),
        (5,35,0),
        (6,5,1),
        (6,8,1),
        (11,5,0),
        (11,11,0),
        (11,20,1),
        (11,36,1),
    ],

    'intermediate' : [
        (1,15,0),
        (1,22,0),
        (1,23,0),
        (2,21,1),
        (3,8,1),
        (3,10,0),
        (3,33,0),
        (4,19,0),
        (5,6,0),
        (5,9,0),
        (5,12,1),
        (6,19,1),
        (6,24,1),
        (7,18,1),
        (8,5,1),
        (8,17,1),
        (8,21,1),
        (9,5,1),
        (9,17,1),
        (10,9,0),
        (10,31,1),
        (10,35,0),
    ],

    'advanced' : [
        (1,20,0),
        (2,21,1),
        (2,23,0),
        (2,36,1),
        (2,37,1),
        (3,14,0),
        (3,25,1),
        (4,20,1),
        (4,34,0),
        (4,35,1),
        (5,16,0),
        (6,16,0),
        (6,16,1),
        (6,21,0),
        (7,22,1),
        (7,40,1),
        (8,17,1),
        (8,23,1),
        (8,27,0),
        (8,33,0)
    ],
}
executor = ThreadPoolExecutor(max_workers=12)

def analyze_positions(json_file, targets,cluster):
    """
    targets: list of (game_index, full_move_number, is_black_turn)
    """
    with open(json_file, "r", encoding="utf-8") as f:
        games = json.load(f)

    IMG_DIR = os.path.join(os.path.dirname(json_file), "analysis_images")
    os.makedirs(IMG_DIR, exist_ok=True)

    output_rows = []
    OUTPUT_FILE = os.path.join(os.path.dirname(json_file), f"selected_{cluster}_moves.tsv")
    for game_idx, full_move, is_black in tqdm(targets):
        game = chess.pgn.read_game(io.StringIO(games[game_idx]["game"]))

        board = game.board()

        target_ply = (full_move - 1) * 2 + is_black

        for ply, move in enumerate(game.mainline_moves()):

            before_fen = board.fen()
            board.push(move)
            after_fen = board.fen()

            if ply == target_ply:
                stockfish_output = expert_struct_output(before_fen, after_fen)
                prompt = process_prompt(stockfish_output)

                row_id = f"g{game_idx}_m{ply}"
                img_path = os.path.join(IMG_DIR, row_id + ".png")

                future = executor.submit(
                    analysis_to_png,
                    stockfish_output.copy(),
                    '',
                    img_path
                )

                output_rows.append({
                    'row_id': row_id,
                    'before_fen': before_fen,
                    'after_fen': after_fen,
                    'move': stockfish_output['played_move'],
                    'prompt': prompt,
                    'analyse': '',
                    'analyser': '',
                    'move type': stockfish_output['move_type'],
                    'move evaluation': stockfish_output['move_evaluation'],
                })
                break


    df = pd.DataFrame(output_rows)
    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding='utf-8',
        header=not os.path.exists(OUTPUT_FILE),
        sep="\t"
    )

for key, filename in OUTPUTS.items():
    analyze_positions(filename, selected_moves[key],key)

engine.quit()
executor.shutdown(wait=True)