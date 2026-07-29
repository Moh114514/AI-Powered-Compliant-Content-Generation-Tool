import React from "react";
import { formatElapsed } from "../hooks/useElapsedSeconds";

export function OperationProgress({ label, elapsedSeconds }: { label: string; elapsedSeconds: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="card"
      style={{
        marginBottom: 12,
        padding: "10px 12px",
        color: "#1d4ed8",
        borderColor: "#bfdbfe",
        background: "#eff6ff",
        display: "flex",
        alignItems: "center",
        gap: 9,
        fontSize: 13,
      }}
    >
      <span
        aria-hidden="true"
        style={{ width: 9, height: 9, borderRadius: "50%", background: "#2563eb", boxShadow: "0 0 0 4px #dbeafe" }}
      />
      <span>{label}，已运行 <b style={{ fontVariantNumeric: "tabular-nums" }}>{formatElapsed(elapsedSeconds)}</b>。模型响应可能需要一些时间，请耐心等待或点击停止。</span>
    </div>
  );
}
