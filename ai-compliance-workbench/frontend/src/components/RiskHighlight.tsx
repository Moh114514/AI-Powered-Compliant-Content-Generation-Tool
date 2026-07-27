import React from "react";
import { segmentText } from "../utils/highlight";
import type { HighlightSpan } from "../types";

export function RiskHighlight({
  text,
  spans,
  onSelect,
}: {
  text: string;
  spans: HighlightSpan[];
  onSelect?: (span: HighlightSpan) => void;
}) {
  const segs = segmentText(text, spans || []);
  return (
    <span style={{ whiteSpace: "pre-wrap", lineHeight: 1.9 }}>
      {segs.map((s, i) =>
        s.hit ? (
          <mark
            key={i}
            className="risk-hit"
            title={`命中：${s.hit.matched_text}（${s.hit.rule_id}）`}
            onClick={() => onSelect && onSelect(s.hit!)}
            style={{ cursor: onSelect ? "pointer" : "default" }}
          >
            {s.text}
          </mark>
        ) : (
          <React.Fragment key={i}>{s.text}</React.Fragment>
        )
      )}
    </span>
  );
}
