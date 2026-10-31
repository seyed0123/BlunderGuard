import React, { useRef, useState} from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";

export default function ChessBoard({ onPositionChange }) {
  const chessGameRef = useRef(new Chess());
  const chessGame = chessGameRef.current;

  const [chessPosition, setChessPosition] = useState(chessGame.fen());
  const [moveFrom, setMoveFrom] = useState("");
  const [optionSquares, setOptionSquares] = useState({});

  // -------------------------
  // Helpers
  // -------------------------

  const makeMove = (from, to) => {
    const game = chessGameRef.current;
    try {
      // Save current FEN as "before"
      const before = game.fen();
      game.move({ from, to, promotion: "q" });
      const after = game.fen();

      setChessPosition(after);

      // Notify parent with both FENs
      if (onPositionChange) {
        onPositionChange({ before, after });
      }
      return true;
    } catch (e) {
      console.error("Invalid move", e);
      return false;
    }
  };

  function getMoveOptions(square) {
    const moves = chessGame.moves({
      square,
      verbose: true,
    });

    if (moves.length === 0) {
      setOptionSquares({});
      return false;
    }

    const newSquares = {};

    for (const move of moves) {
      newSquares[move.to] = {
        background:
          chessGame.get(move.to) &&
          chessGame.get(move.to).color !== chessGame.get(square).color
            ? "radial-gradient(circle, rgba(0,0,0,.1) 85%, transparent 85%)"
            : "radial-gradient(circle, rgba(0,0,0,.1) 25%, transparent 25%)",
        borderRadius: "50%",
      };
    }

    newSquares[square] = {
      background: "rgba(255, 255, 0, 0.4)",
    };

    setOptionSquares(newSquares);
    return true;
  }

  // -------------------------
  // CLICK MOVE (same as source)
  // -------------------------
  function onSquareClick({
    square,
    piece
  }: SquareHandlerArgs) {
    // piece clicked to move
    if (!moveFrom && piece) {
      // get the move options for the square
      const hasMoveOptions = getMoveOptions(square );

      // if move options, set the moveFrom to the square
      if (hasMoveOptions) {
        setMoveFrom(square);
      }

      // return early
      return;
    }

    // square clicked to move to, check if valid move
    const moves = chessGame.moves({
      square: moveFrom ,
      verbose: true
    });
    const foundMove = moves.find(m => m.from === moveFrom && m.to === square);

    // not a valid move
    if (!foundMove) {
      // check if clicked on new piece
      const hasMoveOptions = getMoveOptions(square );

      // if new piece, setMoveFrom, otherwise clear moveFrom
      setMoveFrom(hasMoveOptions ? square : '');

      // return early
      return;
    }
    
    // update the position state
    setChessPosition(chessGame.fen());
    const success = makeMove(moveFrom, square);
    if (!success) return;
    // clear moveFrom and optionSquares
    setMoveFrom('');
    setOptionSquares({});
  }

  // -------------------------
  // DRAG & DROP (same as source)
  // -------------------------
  function onPieceDrop({ sourceSquare, targetSquare }) {
    if (!targetSquare) return false;

    try {
      chessGame.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: "q",
      });

      setChessPosition(chessGame.fen());
      makeMove(sourceSquare, targetSquare);
      setMoveFrom("");
      setOptionSquares({});
      return true;
    } catch {
      return false;
    }
  }


  const chessboardOptions = {
    id: "click-or-drag",
    position: chessPosition,
    onPieceDrop,
    onSquareClick,
    squareStyles: optionSquares,
  };

  return (
      <Chessboard
        options={chessboardOptions}
      />
  );
  
}
