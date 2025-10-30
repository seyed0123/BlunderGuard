import json
from tqdm import tqdm
import csv
from expert import get_best_moves,engine

if __name__ == '__main__': 
    try:
        with open('dataset\chess_commentary_cleaned_combined.json', 'r') as file:
            data = json.load(file)
        print("Data loaded from file:")
    except FileNotFoundError:
        print("Error: The file 'data.json' was not found.")
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON from the file. Check for malformed JSON.")

    games = []
    current_game = []
    for entry in data:
        move_num = int(entry['input'].split('|')[0].split(':')[1].strip())
        if move_num == 1 and current_game:
            games.append(current_game)
            current_game = []
        current_game.append(entry)
    if current_game:
        games.append(current_game)
        
    output_rows = []    
    for game in tqdm(games, desc="Processing games"):
        move_history = []  
        for entry in game:
            
            parts = [part.strip() for part in entry['input'].split('|')]
            move_num = int(parts[0].split(':')[1])
            current_move = parts[1].split(':')[1].strip()
            current_player = parts[2].split(':')[1].strip()
            move_history.append(current_move)
            

            prompt = get_best_moves(move_history)


            commentary = entry['output']

            output_rows.append({
                'prompt': prompt,
                'commentary': commentary
            })

            


    with open('chess_coach_dataset.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['prompt', 'commentary'])
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"✅ Saved {len(output_rows)} entries to 'chess_coach_dataset.csv'")

    engine.quit()