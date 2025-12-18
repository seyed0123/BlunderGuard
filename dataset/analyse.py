import chess

def pawn_structure(board, is_white):
    """
    Collect pawn structure info in one board scan.
    Returns per-file pawn ranks.
    """
    pawns = [[] for _ in range(8)]

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == is_white and piece.piece_type == chess.PAWN:
            f = chess.square_file(sq)
            r = chess.square_rank(sq)
            pawns[f].append(r)

    return pawns

def analyze_pawn_structure(before_board, after_board, is_white):
    """
    Detect doubled, isolated, and backward pawns.
    One board scan total.
    """
    before_pawns = pawn_structure(before_board,is_white)
    after_pawns = pawn_structure(after_board,is_white)

    direction = 1 if is_white else -1

    doubled = []
    isolated = []
    backward = []

    for f in range(8):
        file_name = chr(ord('a') + f)

        before_file = before_pawns[f]
        after_file = after_pawns[f]

        # ======================
        # Doubled pawns (NEW)
        # ======================
        if len(after_file) > 1 and len(after_file) > len(before_file):
            doubled.append(f"{file_name}-file")

        # ======================
        # Isolated pawns (NEW)
        # ======================
        if after_file:
            left_after = after_pawns[f - 1] if f > 0 else []
            right_after = after_pawns[f + 1] if f < 7 else []

            left_before = before_pawns[f - 1] if f > 0 else []
            right_before = before_pawns[f + 1] if f < 7 else []

            was_isolated = not left_before and not right_before
            is_isolated = not left_after and not right_after

            if is_isolated and not was_isolated:
                isolated.append(f"{file_name}-file")

        # ======================
        # Backward pawns (NEW)
        # ======================
        left = after_pawns[f - 1] if f > 0 else []
        right = after_pawns[f + 1] if f < 7 else []

        for rank in after_file:
            next_rank = rank + direction
            if not (0 <= next_rank <= 7):
                continue

            blocked = after_board.piece_at(
                chess.square(f, next_rank)
            ) is not None

            supported = any(p >= rank for p in left + right)

            # Check if this pawn was already backward before
            was_backward = False
            if rank in before_file:
                before_blocked = before_board.piece_at(
                    chess.square(f, rank + direction)
                ) is not None

                before_supported = any(
                    p >= rank for p in
                    ((before_pawns[f - 1] if f > 0 else []) +
                     (before_pawns[f + 1] if f < 7 else []))
                )

                was_backward = before_blocked and not before_supported

            if blocked and not supported and not was_backward:
                backward.append(f"{file_name}-file")
                break  # report file once

    pawn_weakness = bool(doubled or isolated or backward)

    pawn_weakness_details = {
        "doubled": doubled,
        "isolated": isolated,
        "backward": backward
    }

    return pawn_weakness, pawn_weakness_details


def get_played_move(before_fen, after_fen):
    """Extract the move played between two FEN positions"""
    before_board = chess.Board(before_fen)
    after_board = chess.Board(after_fen)
    
    # Try to find the move by comparing legal moves
    for move in before_board.legal_moves:
        test_board = before_board.copy()
        test_board.push(move)
        if test_board.fen().split()[0] == after_board.fen().split()[0]:
            try:
                return before_board.san(move)
            except:
                return move.uci()
    return None

def combined_eval_quality_text(delta, side_text):
    """Combine eval_change and move_quality into a single descriptive text"""
    quality = None
    if delta > 30:
        quality = "Great"
        direction = "significantly improved"
    elif delta > 10:
        quality = "Good"
        direction = "improved"
    elif delta > -10:
        quality = "Normal"
        if abs(delta) < 0.05:
            return f"This was a {quality.lower()} move. The position stayed about the same after this move."
        direction = "slightly changed"
    elif delta > -30:
        quality = "Mistake"
        direction = "worsened"
    else:
        quality = "Blunder"
        direction = "significantly worsened"
    
    if abs(delta) < 0.05:
        return f"This was a {quality.lower()} move. The position stayed about the same after this move."
    
    if delta > 0:
        return f"This was a {quality.lower()} move. The position {direction} for {side_text} after this move."
    else:
        return f"This was a {quality.lower()} move. The position {direction} for {side_text} after this move."

def has_hanging_piece(board, is_white):
    """
    Detect hanging pieces and report piece type + square.
    """
    hanging = []

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece or piece.color != is_white:
            continue

        attackers = board.attackers(not is_white, square)
        defenders = board.attackers(is_white, square)

        if attackers and not defenders:
            piece_name = chess.piece_name(piece.piece_type)
            square_name = chess.square_name(square)
            hanging.append(f"{piece_name} on {square_name}")

    return len(hanging) > 0, hanging


def castling_rights_worsened(before_board, after_board, is_white):
    """
    Detect bad loss of castling rights (not due to castling).
    """
    before_rights = before_board.has_castling_rights(is_white)
    after_rights = after_board.has_castling_rights(is_white)

    if not before_rights or after_rights:
        return False, None

    # Detect if king actually castled
    before_king = before_board.king(is_white)
    after_king = after_board.king(is_white)

    if before_king and after_king:
        if abs(chess.square_file(before_king) - chess.square_file(after_king)) == 2:
            # This WAS castling → not a weakness
            return False, None

    return True, "Lost the ability to castle"

def pawn_shield(board, king_square, is_white):
    """
    Count friendly pawns directly in front of the king.
    """
    if king_square is None:
        return 0

    rank = chess.square_rank(king_square)
    file = chess.square_file(king_square)

    shield_rank = rank + 1 if is_white else rank - 1
    if shield_rank < 0 or shield_rank > 7:
        return 0

    count = 0
    for df in [-1, 0, 1]:
        f = file + df
        if 0 <= f <= 7:
            sq = chess.square(f, shield_rank)
            piece = board.piece_at(sq)
            if piece and piece.color == is_white and piece.piece_type == chess.PAWN:
                count += 1

    return count

def king_safety_worsened(before_board, after_board, is_white):
    """
    Detect king safety deterioration using:
    - Bad castling rights loss
    - Increased direct attacks
    - Weakened pawn shield
    """
    # 1. Castling rights
    lost_castling, reason = castling_rights_worsened(
        before_board, after_board, is_white
    )
    if lost_castling:
        return True, reason

    before_king = before_board.king(is_white)
    after_king = after_board.king(is_white)

    if not before_king or not after_king:
        return False, None

    # 2. Attack balance
    before_pressure = (
        len(before_board.attackers(not is_white, before_king)) -
        len(before_board.attackers(is_white, before_king))
    )
    after_pressure = (
        len(after_board.attackers(not is_white, after_king)) -
        len(after_board.attackers(is_white, after_king))
    )

    if after_pressure > before_pressure and after_pressure > 0:
        return True, "King came under more pressure"

    # 3. Pawn shield
    before_shield = pawn_shield(before_board, before_king, is_white)
    after_shield = pawn_shield(after_board, after_king, is_white)

    if after_shield < before_shield:
        return True, "Pawn shield in front of the king was weakened"

    return False, None


def center_control_lost(before_board, after_board, is_white):
    """Check if center control was lost"""
    center_squares = [chess.E4, chess.E5, chess.D4, chess.D5]
    
    before_control = sum(1 for sq in center_squares if before_board.attackers(is_white, sq))
    after_control = sum(1 for sq in center_squares if after_board.attackers(is_white, sq))
    
    # Also check if opponent gained more control
    before_opp_control = sum(1 for sq in center_squares if before_board.attackers(not is_white, sq))
    after_opp_control = sum(1 for sq in center_squares if after_board.attackers(not is_white, sq))
    
    if after_control < before_control or after_opp_control > before_opp_control:
        return True, "Center control weakened"
    return False, None

def development_slowed(before_board, after_board, is_white):
    """Check if piece development was slowed (knights/bishops still on starting squares)"""
    # Check knights (should be on b1/g1 for white, b8/g8 for black)
    if is_white:
        knight_squares = [chess.B1, chess.G1]
        bishop_squares = [chess.C1, chess.F1]
        back_rank = 0
    else:
        knight_squares = [chess.B8, chess.G8]
        bishop_squares = [chess.C8, chess.F8]
        back_rank = 7
    
    before_knights = sum(1 for sq in knight_squares if before_board.piece_at(sq) and before_board.piece_at(sq).piece_type == chess.KNIGHT)
    after_knights = sum(1 for sq in knight_squares if after_board.piece_at(sq) and after_board.piece_at(sq).piece_type == chess.KNIGHT)
    
    before_bishops = sum(1 for sq in bishop_squares if before_board.piece_at(sq) and before_board.piece_at(sq).piece_type == chess.BISHOP)
    after_bishops = sum(1 for sq in bishop_squares if after_board.piece_at(sq) and after_board.piece_at(sq).piece_type == chess.BISHOP)
    
    # If more pieces are still on starting squares after the move
    if (after_knights + after_bishops) > (before_knights + before_bishops):
        return True, "Development delayed"
    return False, None


def extract_position_features(before_fen, after_fen, is_white):
    """Extract key position features"""
    before_board = chess.Board(before_fen)
    after_board = chess.Board(after_fen)
    
    features = {}
    
    # Hanging piece
    has_hanging, hanging_squares = has_hanging_piece(after_board, is_white)
    features["hanging_piece"] = has_hanging
    if has_hanging:
        features["hanging_piece_details"] = hanging_squares
    
    # King safety
    king_worse, king_reason = king_safety_worsened(before_board, after_board, is_white)
    features["king_safety_status"] = king_worse
    if king_worse:
        features["king_safety_details"] = king_reason
    
    # Center control
    center_lost, center_reason = center_control_lost(before_board, after_board, is_white)
    features["center_control_status"] = center_lost
    if center_lost:
        features["center_control_details"] = center_reason
    
    # Development
    dev_slowed, dev_reason = development_slowed(before_board, after_board, is_white)
    features["development_status"] = dev_slowed
    if dev_slowed:
        features["development_details"] = dev_reason
        
    pawn_weakness, pawn_weakness_details = analyze_pawn_structure(
        before_board, after_board, is_white
    )
    features["pawn_structure_status"] = pawn_weakness
    if pawn_weakness:
        features["pawn_structure_details"] = pawn_weakness_details
    
    return features