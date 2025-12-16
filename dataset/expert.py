import chess
import chess.engine
import math
import random

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

    random_depth = random.randint(18, 21)

    info_list = engine.analyse(
        board,
        chess.engine.Limit(depth=random_depth),
        info=chess.engine.INFO_ALL,
        multipv=moves_num
    )

    for i, info in enumerate(info_list):

        if "pv" not in info:
            output += "[White POV]: no PV (lost position)\n"
            continue

        pv_san = []
        temp_board = board.copy()

        for move in info["pv"]:
            try:
                pv_san.append(temp_board.san(move))
                temp_board.push(move)
            except:
                pv_san.append(move.uci())
                break

        win_prob, cp = score_to_winprob(info["score"])
        depth = info.get("depth", 0)

        if best is None:
            best = win_prob
        else:
            best = max(best, win_prob)

        pv_str = " ".join(pv_san[:20])

        output += (
            f"[White POV]: {win_prob:.1f}% "
            f"cp:{cp} {pv_str} (Depth: {depth})\n"
        )

    return output, fen, str(best)


# engine.quit()