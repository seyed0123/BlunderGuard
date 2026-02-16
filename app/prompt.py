SINGLE_METHOD = """
You are a chess coach explaining a move to a beginner.

IMPORTANT RULES (must follow):
- Write only 2 or 3 short sentences.
- Use simple, natural language.
- Do NOT mention move names or chess notation.
- Do NOT mention numbers, evaluations, or engine terms.
- Do NOT quote engine lines.
- Explain ideas, not calculations.

Key position changes detected (this information is correct and important):

White:
{position_features_white}

Black:
{position_features_black}

Engine analysis context (for understanding only, do not mention directly):

Before move:
{before_stockfish_analysis}

After move:
{after_stockfish_analysis}

Checkmate status after the move:
{checkmate}


Now explain why this move weakened or improved the position.
Focus on king safety, piece coordination, control of the board, and threats.
"""

FINAL_CHAIN_METHOD = """
You are a chess position evaluator.

Win probabilities are from White’s perspective.

TASK:
Compare the position BEFORE and AFTER the move.
Decide whether the move improved or weakened the position,
and explain WHY.

RULES (must follow):
- Write only 2 or 3 sentences.
- Use plain natural language.
- Do NOT mention move names or chess notation.
- Do NOT mention numbers, evaluations, or engine terms.
- Write in a way that a chess beginner can understand.

Before position:
{before_position}

After position:
{after_position}

Position description BEFORE the move:
{position_description_before}

Position description AFTER the move:
{position_description_after}

Key position changes detected:

White:
{position_features_white}

Black:
{position_features_black}

Engine analysis context (for understanding only, do not mention directly):

Before move:
{before_stockfish}

After move:
{after_stockfish}

Checkmate status after the move:
{checkmate_status}

Now explain why this move made the position better or worse.
Focus on king safety, piece coordination, board control, and threats.
"""

POSITION_CHAIN_METHOD = """
You are a chess engine. 

Describe the position in terms of these aspects: 
1. Central control
2. Piece activity
3. King safety
4. Pawn structure
5. Initiative

Use 1 sentence per aspect.

Position:
{analysis}
"""