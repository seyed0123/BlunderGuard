import React from "react";

export default function AnalysisPanel({ analysis }) {
  const { loading, data, error } = analysis;

  return (
    <div
      style={{
        width:'80%',
        maxHeight: "100vh",
        overflowY: "auto",
        backgroundColor: "#f8f9fa",
        border: "1px solid #ddd",
        borderRadius: "8px",
        padding: "16px",
        fontSize: "14px",
        lineHeight: "1.6",
        boxShadow: "0 2px 6px rgba(0,0,0,0.05)",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <h3
        style={{
          margin: 0,
          color: "#333",
          borderBottom: "1px solid #eee",
          paddingBottom: "8px",
        }}
      >
        📊 Game Analysis
      </h3>

      {loading ? (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              width: "16px",
              height: "16px",
              border: "2px solid #ccc",
              borderTopColor: "#007bff",
              borderRadius: "50%",
              animation: "spin 1s linear infinite",
            }}
          ></div>
          <span>Analyzing position...</span>
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      ) : error ? (
        <div style={{ color: "#d32f2f" }}>
          ❌ Failed to analyze: {error}
        </div>
      ) : data ? (
        <div style={{ color: "#222" }}>
          {data.text
            ? data.text
                .split(". ") // split by sentences
                .map((sentence, idx) => (
                  <p key={idx} style={{ margin: "6px 0" }}>
                    {sentence.trim()}.
                  </p>
                ))
            : "No analysis available."}
        </div>
      ) : (
        <div>No analysis available.</div>
      )}
    </div>
  );
}
