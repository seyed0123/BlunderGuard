import shutil
import tempfile
import threading

import chess
import chess.svg
import ipywidgets as widgets
import os
from playwright.sync_api import sync_playwright
from ipywidgets.embed import embed_minimal_html
import uuid

_widget_lock = threading.Lock()

def board_widget(fen, move=None, size=350):
    board = chess.Board(fen)

    svg = chess.svg.board(
        board,
        size=size,
        lastmove=move
    )

    return widgets.HTML(value=svg)


def labeled_board(title, fen, move=None):
    label = widgets.HTML(
        value=f"""
        <div style="
            text-align:center;
            font-weight:bold;
            margin-bottom:6px;
            font-size:16px;
        ">
            {title}
        </div>
        """
    )

    board = board_widget(fen, move)

    return widgets.VBox(
        [label, board],
        layout=widgets.Layout(align_items="center")
    )


def analysis_widget(sample, llm_output):
    before_board = chess.Board(sample["before"]["fen"])
    move = before_board.parse_san(sample["played_move"])

    before_block = labeled_board(
        "Before position",
        sample["before"]["fen"],
        move
    )

    after_block = labeled_board(
        "After position",
        sample["after"]["fen"]
    )

    boards_row = widgets.HBox(
        [before_block, after_block],
        layout=widgets.Layout(
            justify_content="center",
            gap="40px"
        )
    )

    # Move type badge (color-coded)
    move_type = sample.get("move_evaluation", "unknown").capitalize()
    move_colors = {
        "Blunder": "#d9534f",
        "Mistake": "#f0ad4e",
        "Inaccuracy": "#f7c948",
        "Normal": "#5bc0de",
        "Good": "#5cb85c"
    }
    color = move_colors.get(move_type, "#999")

    move_type_badge = widgets.HTML(
        value=f"""
        <div style="
            display:inline-block;
            margin:12px 0 6px 0;
            padding:4px 10px;
            border-radius:12px;
            font-size:13px;
            font-weight:bold;
            color:white;
            background:{color};
        ">
            {move_type}
        </div>
        """
    )

    # LLM text (left-aligned, symmetric)
    text = widgets.HTML(
        value=f"""
        <div style="
            margin-top:6px;
            padding:8px 12px;
            border:1px solid #ddd;
            border-radius:6px;
            font-family:Arial, sans-serif;
            font-size:14px;
            line-height:1.5;
            text-align:left;
            background:#fafafa;
        ">
            <div style="margin-left:16px;">
                {llm_output}
            </div>
        </div>
        """
    )

    return(
        widgets.VBox(
            [
                boards_row,
                widgets.HBox([move_type_badge], layout=widgets.Layout(justify_content="center")),
                text
            ]
        )
    )

def analysis_to_png(sample, llm_output, output_path="output.png"):
    # temporary html file
    with _widget_lock:

        widget = analysis_widget(sample, llm_output)
        temp_dir = tempfile.mkdtemp(prefix="chess_analysis_")
        html_path = os.path.join(temp_dir, f"analysis_{uuid.uuid4().hex[:16]}.html")
        embed_minimal_html(
            html_path,
            views=[widget],
            title="Chess Analysis"
        )

    try:
        with sync_playwright() as p:
            browser = p.firefox.launch()
            page = browser.new_page()

            page.goto(f"file://{os.path.abspath(html_path)}")
            page.wait_for_timeout(1000)  # wait for render

            page.screenshot(path=output_path, full_page=True)

            browser.close()

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)