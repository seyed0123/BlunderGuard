import React, { useState } from "react";
import Chessboard from "chessboardjsx";
import Chess from "chess.js";

const BACKEND_URL = "http://127.0.0.1:8000"; // Flask backend

export default function ChessBoard() {
  const [game] = useState(new Chess());
  const [fen, setFen] = useState("start");
  const [analysis, setAnalysis] = useState("");

  const onDrop = ({ sourceSquare, targetSquare, piece }) => {
    const move = game.move({
      from: sourceSquare,
      to: targetSquare,
      promotion: "q"
    });

    if (move === null) return false; // invalid move

    setFen(game.fen());
    setAnalysis(""); // clear previous analysis
  };

  const analyzeMove = async () => {
    const history = game.history({ verbose: true });
    if (history.length < 1) {
      alert("Make a move first!");
      return;
    }

    const beforeFEN = history.length > 1 ? game.fen() : "start";
    const afterFEN = game.fen();

    setAnalysis("⏳ Analyzing...");

    try {
      const response = await fetch(`${BACKEND_URL}/single`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          before: beforeFEN,
          after: afterFEN
        })
      });

      if (!response.ok) throw new Error("Network response was not OK");

      const data = await response.json();
      setAnalysis(data.text);
    } catch (err) {
      console.error(err);
      setAnalysis("❌ Error analyzing move");
    }
  };

  return (
    <div style={{ textAlign: "center", marginTop: 20 }}>
      <h2>Chess Blunder Guard</h2>
      <Chessboard
        width={400}
        position={fen}
        onDrop={onDrop}
      />
      <div style={{ marginTop: 10 }}>
        <button onClick={analyzeMove}>Analyze Move</button>
      </div>
      <pre
        style={{
          marginTop: 10,
          maxWidth: 400,
          marginLeft: "auto",
          marginRight: "auto",
          textAlign: "left",
          background: "#f4f4f4",
          padding: 10,
          borderRadius: 5
        }}
      >
        {analysis}
      </pre>
    </div>
  );
}
