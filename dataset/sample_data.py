from expert import get_best_moves,engine
import json

INPUT_FILE = "./moves.txt"
OUTPUT_FILE = "./moves_labeled.json"

file = open(INPUT_FILE, "r")
move_type,move_number = None,None
AFEN,BFEN = None,None
outputs = []
with open(INPUT_FILE, "r") as file, open(OUTPUT_FILE, "a", encoding="utf-8") as out:
    for line in file:
        if move_type == None:
            move_type,move_number = line.strip().split()
        elif BFEN == None:
            BFEN = line.strip()
        elif AFEN == None:
            AFEN = line.strip()
        else:
            before_analysis, before_fen, before_eval = get_best_moves(BFEN)
            after_analysis, after_fen, after_eval = get_best_moves(AFEN)
            
            sample = {
                "move_type": move_type,
                "move_number": int(move_number),

                "before": {
                    "fen": before_fen,
                    "stockfish_analysis": before_analysis.strip(),
                    "eval": before_eval
                },

                "after": {
                    "fen": after_fen,
                    "stockfish_analysis": after_analysis.strip(),
                    "eval": after_eval
                }
            }
            outputs.append(sample)
            
            AFEN,BFEN = None,None
            move_type,move_number = None,None

    out.write(json.dumps(outputs, indent=2, ensure_ascii=False))            
engine.quit()