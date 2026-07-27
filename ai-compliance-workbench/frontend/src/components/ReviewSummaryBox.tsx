import React from "react";
import { Copy, Download } from "lucide-react";
import { copyText, downloadText } from "../utils/misc";

export function ReviewSummaryBox({ summary, title = "人工复核摘要" }: { summary: string; title?: string }) {
  return (
    <div className="card" style={{ background: "#faf9ff" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <strong style={{ fontSize: 14 }}>{title}</strong>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className="btn"
            style={{ padding: "4px 8px", fontSize: 12 }}
            onClick={async () => {
              const ok = await copyText(summary);
              alert(ok ? "已复制到剪贴板" : "复制失败");
            }}
          >
            <Copy size={14} /> 复制
          </button>
          <button
            className="btn"
            style={{ padding: "4px 8px", fontSize: 12 }}
            onClick={() => downloadText("复核摘要.txt", summary, "text/plain")}
          >
            <Download size={14} /> TXT
          </button>
          <button
            className="btn"
            style={{ padding: "4px 8px", fontSize: 12 }}
            onClick={() => downloadText("复核摘要.md", summary, "text/markdown")}
          >
            <Download size={14} /> MD
          </button>
        </div>
      </div>
      <pre
        style={{
          whiteSpace: "pre-wrap",
          fontSize: 13,
          color: "#374151",
          margin: 0,
          fontFamily: "inherit",
        }}
      >
        {summary}
      </pre>
    </div>
  );
}
