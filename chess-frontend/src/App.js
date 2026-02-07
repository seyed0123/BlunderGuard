// App.js
import React, { useState } from "react";
import ChessBoard from "./ChessBoard";
import AnalysisPanel from "./AnalysisPanel";

function App() {
  const [analysis, setAnalysis] = useState({
    loading: false,
    data: null,
    error: null,
  });

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        minHeight: "100vh",
        padding: "24px",
        boxSizing: "border-box",
        gap: "32px",
      }}
    >
    <AnalysisPanel analysis={analysis} />
    <div style={{width:'90%'}}>
      <ChessBoard
        onPositionChange={({ before, after }) => {
          setAnalysis({ loading: true, data: null, error: null });

          fetch("/single", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ before, after }),
          })
            .then(res => {
              if (!res.ok) throw new Error("Server error");
              return res.json();
            })
            .then(data => {
              setAnalysis({ loading: false, data, error: null });
            })
            .catch(err => {
              setAnalysis({ loading: false, data: null, error: err.message });
            });
        }}
      />
      </div>
      

      
    </div>
  );
}

export default App;