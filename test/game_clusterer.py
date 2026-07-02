import chess.pgn
import json

PGN_FILE = "../dataset/lichess_db_standard_rated_2013-02.pgn"

OUTPUTS = {
    "noob": "noob/noob.json",
    "intermediate": "intermediate/intermediate.json",
    "advanced": "advanced/advanced.json",
}

clusters = {
    "noob": [],
    "intermediate": [],
    "advanced": [],
}


if __name__ == "__main__":
    with open(PGN_FILE, encoding="utf-8") as pgn:
        while True:
            game = chess.pgn.read_game(pgn)

            if game is None:
                break

            num_plies = sum(1 for _ in game.mainline_moves())

            if num_plies < 30:
                continue

            try:
                white = int(game.headers["WhiteElo"])
                black = int(game.headers["BlackElo"])
            except:
                continue

            avg_elo = (white + black) / 2

            if avg_elo < 1200:
                key = "noob"
            elif avg_elo < 1800:
                key = "intermediate"
            else:
                key = "advanced"

            if len(clusters[key]) >= 20:
                if all(len(v) >= 20 for v in clusters.values()):
                    break
                continue

            exporter = chess.pgn.StringExporter(
                headers=False,
                variations=False,
                comments=False,
            )

            clusters[key].append({
                "avg_elo": avg_elo,
                "game": game.accept(exporter),
            })

    # Save each cluster to its own file
    for key, filename in OUTPUTS.items():
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(clusters[key], f, indent=2)

        print(f"{filename}: {len(clusters[key])} games")