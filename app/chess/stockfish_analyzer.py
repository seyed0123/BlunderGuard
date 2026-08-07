import chess
import chess.engine
import math
import random
from app.chess.position_analysis import *
from dotenv import load_dotenv
import os
load_dotenv()

engine_path=os.getenv('stockfish_path')
engine_path='/usr/games/stockfish'
engine = chess.engine.SimpleEngine.popen_uci(engine_path)
engine.configure({
    "Threads": 14,
    "Hash": 2048,
})

def score_to_winprob(score):
    """
    Convert engine score to White win probability (0–100%)
    """
    pov = score.white()   # ALWAYS from White's perspective

    if pov.is_mate():
        mate_in = pov.mate()
        cp = 10000 if mate_in > 0 else -10000
        win_prob = 100.0 if mate_in > 0 else 0.0
        return win_prob, cp

    cp = pov.score()
    if cp is None:
        return 50.0, 0

    # Logistic-like scaling
    win_prob = 50.0 + 50.0 * math.tanh(cp / 250.0)
    return win_prob, cp

    




def get_best_moves(fen,max_time, moves_num=3,):
    board = chess.Board(fen)
    output = ''
    best = None
    best_move = None
    is_white_turn = board.turn
    mate_info = None  # (has_mate, mate_length, mated_side)

    info_list = engine.analyse(
        board,
        chess.engine.Limit(depth=17),
        info=chess.engine.INFO_ALL,
        multipv=moves_num
    )

    if isinstance(info_list, dict):
        info_list = [info_list]

    for i, info in enumerate(info_list):
        score = info.get("score")
        if score is None:
            continue
        pov = score.white()

        if pov.is_mate() and pov.mate() == 0:
            mated_side = "White" if is_white_turn else "Black"

            mate_info = (True, 0, mated_side)

            best = 10000.0 if mated_side == "Black" else -10000.0

            output += f"Checkmate on board\n"
            break

        first_move = info["pv"][0]
        is_best = (i == 0)



        win_prob, cp = score_to_winprob(info["score"])
        depth = info.get("depth", 0)
        win_prob = round(win_prob, 2)

        if "pv" in info and len(info["pv"]) > 0 and is_best:
            try:
                best=cp/100
                best_move = board.san(first_move)
            except:
                best_move = first_move.uci()

        pv_str = " ".join(move.uci() for move in info["pv"])
        # Mate detection (only from best line, PV[0])
        pov = score.white()
        if is_best:
            if pov.is_mate():
                mate_in = pov.mate()

                if mate_in > 0:
                    mate_info = (True, mate_in, "Black")  # White is mating
                else:
                    mate_info = (True, abs(mate_in), "White")  # Black is mating

                output += f"Mate in {abs(mate_in)} moves: {pv_str} (Depth: {depth})\n"
                continue
        
        cp = float(cp)/100
        output += (
            f"[White POV]: {win_prob}% "
            f"cp:{cp} {pv_str} (Depth: {depth})\n"
        )

    return output, fen, best, is_white_turn, best_move, mate_info
    
def expert_struct_output(before_FEN:str,after_FEN:str,move_type=None,move_number=None) ->dict :
    before_analysis, before_fen, before_eval, before_is_white_turn, before_best_move, before_mate_info = get_best_moves(before_FEN,0.3)
    after_analysis, after_fen, after_eval, after_is_white_turn, after_best_move, after_mate_info = get_best_moves(after_FEN,0.1)
    
    # Calculate delta (from the player's perspective who made the move)
    # Positive delta = better for the player, negative = worse
    eval_delta = float(after_eval) - float(before_eval)
    if not before_is_white_turn:
        eval_delta = -eval_delta  # Flip for black's perspective (eval is from White's POV)

    missed_opportunity = None
    if eval_delta < 0:
        missed_opportunity = after_eval * before_eval > 0

    # Get played move
    played_move = get_played_move(before_fen, after_fen)
    
    # Extract position features
    position_features_white = extract_position_features(before_fen, after_fen, True)
    position_features_black = extract_position_features(before_fen, after_fen, False)

    player_to_move = "White" if before_is_white_turn else "Black"

    opp = opportunity(eval_delta,missed_opportunity,player_to_move)
    # Extract checkmate information from after position
    checkmate_info = {
        "unavoidable_checkmate": False
    }
    has_mate = None
    if after_mate_info is not None:
        has_mate, mate_length, mated_side = after_mate_info
        checkmate_info["unavoidable_checkmate"] = has_mate
        if has_mate:
            checkmate_info["mate_length"] = mate_length
            checkmate_info["mated_side"] = mated_side
    move_evaluation,move_type = combined_eval_quality_text(eval_delta, "White" if before_is_white_turn else "Black",None if has_mate is None else has_mate==player_to_move)
    sample = {
        "before": {
            "fen": before_fen,
            "stockfish_analysis": before_analysis.strip(),
            "eval": before_eval,
            "player_to_move": "White" if before_is_white_turn else "Black",
        },

        "after": {
            "fen": after_fen,
            "stockfish_analysis": after_analysis.strip(),
            "eval": after_eval,
            "player_to_move": "White" if after_is_white_turn else "Black",
        },
        "missed_opportunity":opp if opp is not None else None,
        "best_move": before_best_move,
        "after_best_move": after_best_move,
        "played_move": played_move,
        "move_evaluation": move_evaluation,
        "checkmate": checkmate_info,
        "position_features_white": position_features_white,
        "position_features_black": position_features_black,
        "player_to_play":player_to_move
    }
    if move_number:
        sample['move_number'] = int(move_number)
    if move_type:
        sample['move_type'] = move_type
    return sample

# engine.quit()
