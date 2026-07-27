import type { HighlightSpan } from "../types";

export interface Segment {
  text: string;
  hit?: HighlightSpan;
}

// 将原文与命中区间拆分为可渲染的片段（区间已在原文坐标系）。
export function segmentText(text: string, spans: HighlightSpan[]): Segment[] {
  if (!spans || spans.length === 0) return [{ text }];
  const sorted = [...spans].sort((a, b) => a.start_index - b.start_index);
  const segs: Segment[] = [];
  let cursor = 0;
  for (const sp of sorted) {
    const s = Math.max(0, Math.min(sp.start_index, text.length));
    const e = Math.max(s, Math.min(sp.end_index, text.length));
    if (s > cursor) segs.push({ text: text.slice(cursor, s) });
    if (e > s) segs.push({ text: text.slice(s, e), hit: sp });
    cursor = Math.max(cursor, e);
  }
  if (cursor < text.length) segs.push({ text: text.slice(cursor) });
  return segs;
}
