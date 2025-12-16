from expert import get_best_moves,engine,expert_struct_output
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
            outputs.append(expert_struct_output(BFEN,AFEN,move_type,move_number))
            
            AFEN,BFEN = None,None
            move_type,move_number = None,None

    out.write(json.dumps(outputs, indent=2, ensure_ascii=False))            
engine.quit()