import chess
import chess.engine
import math

def score_to_winprob(score, player_color):
    """
    Convert a chess.engine.PovScore to win probability (0–100%) for the player to move.
    """
    
    if player_color == chess.WHITE:
        pov_score = score.white()
    else:
        pov_score = score.black()

    
    if pov_score.is_mate():
        mate_in = pov_score.mate()
        if mate_in > 0:
            return 100.0,math.inf  
        else:
            return 0.0,-math.inf    
    else:

        cp = pov_score.score()
        if cp is None:
            return 50.0,0

        return 50.0 + 50.0 * math.tanh(cp / 400.0),cp
    
engine_path="H:\stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2"
engine = chess.engine.SimpleEngine.popen_uci(engine_path)



def get_best_moves(board,moves_num=3):
        
    fen = board.fen()
    output = f"FEN: {fen}\n"
    best = None
    
    info_list = engine.analyse(
        board,
        chess.engine.Limit(depth=15),
        info=chess.engine.INFO_ALL,
        multipv=moves_num
    )

    for i, info in enumerate(info_list):
        player = "White" if board.turn == chess.WHITE else "Black"
        
        
        if "pv" not in info:
            output+=f"[{player}]: lost the game to the opponent \n "
            continue

        
        pv_san = []
        temp_board = board.copy()
        for move in info["pv"]:
            try:
                san = temp_board.san(move)
                pv_san.append(san)
                temp_board.push(move)
            except Exception as e:
                pv_san.append(move.uci())
                break
    
        win_prob,cp = score_to_winprob(info["score"], board.turn)

        depth = info.get("depth", 0)
        pv_str = " ".join(pv_san[:20])

        if best is None:
            best = win_prob
        else:
            best = max(best,win_prob)
        output += f"[{player}]: {win_prob:.1f}% cp:{cp} {pv_str} (Depth: {depth}) \n "
    return output,player,best

# engine.quit()