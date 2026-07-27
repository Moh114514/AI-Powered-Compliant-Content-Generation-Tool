import React from "react";
import type { RiskMeta } from "../utils/risk";

export function RiskBadge({ meta, size = "sm" }: { meta: RiskMeta; size?: "sm" | "md" }) {
  const pad = size === "md" ? "4px 10px" : "2px 8px";
  const fs = size === "md" ? 13 : 12;
  return (
    <span
      style={{
        backgroundColor: meta.bg,
        color: meta.text,
        border: `1px solid ${meta.border}`,
        borderRadius: 6,
        padding: pad,
        fontSize: fs,
        fontWeight: 600,
        display: "inline-flex",
        alignItems: "center",
        lineHeight: 1.4,
      }}
    >
      {meta.label}
    </span>
  );
}
