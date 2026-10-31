import html

import chess
import chess.svg
from playwright.sync_api import sync_playwright


_MOVE_COLORS = {
    "Blunder": "#d9534f",
    "Mistake": "#f0ad4e",
    "Inaccuracy": "#f7c948",
    "Normal": "#5bc0de",
    "Good": "#5cb85c",
}


def _analysis_html(sample, llm_output, board_size=350):
    """Build a complete, dependency-free HTML document for a position analysis."""
    before_board = chess.Board(sample["before"]["fen"])
    move = before_board.parse_san(sample["played_move"])

    before_svg = chess.svg.board(
        before_board,
        size=board_size,
        lastmove=move,
    )
    after_svg = chess.svg.board(
        chess.Board(sample["after"]["fen"]),
        size=board_size,
    )

    move_type = str(sample.get("move_evaluation", "unknown")).capitalize()
    color = _MOVE_COLORS.get(move_type, "#999")

    # Model output is data, not trusted HTML. Escaping it also prevents malformed
    # model responses from breaking the page used for the screenshot.
    safe_output = html.escape(str(llm_output))
    safe_move_type = html.escape(move_type)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Chess Analysis</title>
  <style>
    html, body {{ margin: 0; background: white; }}
    body {{ padding: 8px; font-family: Arial, sans-serif; }}
    .analysis {{ width: 740px; }}
    .boards {{ display: flex; justify-content: center; gap: 40px; }}
    .board {{ text-align: center; }}
    .title {{ margin-bottom: 6px; font-size: 16px; font-weight: bold; }}
    .badge-row {{ margin: 12px 0 6px; text-align: center; }}
    .badge {{
      display: inline-block; padding: 4px 10px; border-radius: 12px;
      color: white; background: {color}; font-size: 13px; font-weight: bold;
    }}
    .commentary {{
      margin-top: 6px; padding: 8px 12px; border: 1px solid #ddd;
      border-radius: 6px; background: #fafafa; font-size: 14px;
      line-height: 1.5; text-align: left; white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
  <main class="analysis">
    <div class="boards">
      <section class="board"><div class="title">Before position</div>{before_svg}</section>
      <section class="board"><div class="title">After position</div>{after_svg}</section>
    </div>
    <div class="badge-row"><span class="badge">{safe_move_type}</span></div>
    <div class="commentary">{safe_output}</div>
  </main>
</body>
</html>"""


def analysis_to_png(sample, llm_output, output_path="output.png"):
    """Render a chess analysis to PNG without loading any network resources."""
    document = _analysis_html(sample, llm_output)

    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        try:
            page = browser.new_page(viewport={"width": 756, "height": 800})
            page.set_content(document, wait_until="load")
            page.locator(".analysis").screenshot(path=output_path)
        finally:
            browser.close()
