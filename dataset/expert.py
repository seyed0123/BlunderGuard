import chess
import chess.engine
import math
import random
from analyse import *

def score_to_winprob(score):
    """
    Convert engine score to White win probability (0–100%)
    """
    pov = score.white()   # ALWAYS from White's perspective

    if pov.is_mate():
        mate_in = pov.mate()
        if mate_in > 0:
            return 100.0, math.inf   # White mates
        else:
            return 0.0, -math.inf    # Black mates

    cp = pov.score()
    if cp is None:
        return 50.0, 0

    # Logistic-like scaling
    win_prob = 50.0 + 50.0 * math.tanh(cp / 400.0)
    return win_prob, cp

    
engine_path="H:\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2"
engine = chess.engine.SimpleEngine.popen_uci(engine_path)



def get_best_moves(fen, moves_num=3):
    board = chess.Board(fen)
    output = ''
    best = None
    best_move = None
    is_white_turn = board.turn
    mate_info = None  # (has_mate, mate_length, mated_side)

    random_depth = random.randint(18, 21)

    info_list = engine.analyse(
        board,
        chess.engine.Limit(depth=random_depth),
        info=chess.engine.INFO_ALL,
        multipv=moves_num
    )

    for i, info in enumerate(info_list):

        if "pv" not in info:
            output += "[White POV]: no PV checkmate\n"
            continue

        pv_san = []
        temp_board = board.copy()
        first_move = None

        for move in info["pv"]:
            if first_move is None:
                first_move = move
            try:
                pv_san.append(temp_board.san(move))
                temp_board.push(move)
            except:
                pv_san.append(move.uci())
                break

        win_prob, cp = score_to_winprob(info["score"])
        depth = info.get("depth", 0)
        win_prob = int(win_prob*100) / 100
        
        is_best = False
        if best is None:
            best = win_prob
            is_best = True
        else:
            if is_white_turn:
                if win_prob > best:
                    best = win_prob
                    is_best = True
            else:
                if win_prob < best:
                    best = win_prob
                    is_best = True
        
        if is_best and first_move is not None:
            try:
                best_move = board.san(first_move)
            except:
                best_move = first_move.uci()
        
        # Check for mate in the best line
        if is_best:
            score = info.get("score")
            if score is not None:
                pov = score.white()  # From White's perspective
                if pov.is_mate():
                    mate_in = pov.mate()
                    if mate_in > 0:
                        # White is mating Black
                        mate_info = (True, mate_in, "Black")
                    else:
                        # Black is mating White
                        mate_info = (True, abs(mate_in), "White")

        pv_str = " ".join(pv_san[:20])
        if win_prob == 100 or win_prob == 0:
            mate_lenght = len(pv_san)
            output += f"Mate in {mate_lenght} moves: {pv_str} (Depth: {depth})\n"
            continue
        
        cp = float(cp)/100
        output += (
            f"[White POV]: {win_prob}% "
            f"cp:{cp} {pv_str} (Depth: {depth})\n"
        )

    return output, fen, str(best), is_white_turn, best_move, mate_info
    
def expert_struct_output(before_FEN:str,after_FEN:str,move_type=None,move_number=None) ->dict :
    before_analysis, before_fen, before_eval, before_is_white_turn, before_best_move, before_mate_info = get_best_moves(before_FEN)
    after_analysis, after_fen, after_eval, after_is_white_turn, after_best_move, after_mate_info = get_best_moves(after_FEN)
    
    # Calculate delta (from the player's perspective who made the move)
    # Positive delta = better for the player, negative = worse
    eval_delta = float(after_eval) - float(before_eval)
    if not before_is_white_turn:
        eval_delta = -eval_delta  # Flip for black's perspective (eval is from White's POV)
    
    # Get played move
    played_move = get_played_move(before_fen, after_fen)
    
    # Extract position features
    position_features_white = extract_position_features(before_fen, after_fen, False)
    position_features_black = extract_position_features(before_fen, after_fen, True)

    player_to_move = "White" if before_is_white_turn else "Black"
    
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
        "best_move": before_best_move,
        "played_move": played_move,
        "move_evaluation": combined_eval_quality_text(eval_delta, "White" if before_is_white_turn else "Black",None if has_mate is None else has_mate==player_to_move),
        "checkmate": checkmate_info,
        "position_features_white": position_features_white,
        "position_features_black": position_features_black
    }
    if move_number:
        sample['move_number'] = int(move_number)
    if move_type:
        sample['move_type'] = move_type
    return sample

# engine.quit()