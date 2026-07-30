import type { HighlightSpan } from "../types";

export interface Segment {
  text: string;
  hit?: HighlightSpan;
}

const RISK_PRIORITY: Record<string, number> = {
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};

// API 使用 Unicode 码点坐标；JavaScript slice 使用 UTF-16 码元坐标。
function codePointOffsets(text: string): number[] {
  const offsets = [0];
  let codeUnitOffset = 0;
  for (const character of text) {
    codeUnitOffset += character.length;
    offsets.push(codeUnitOffset);
  }
  return offsets;
}

// 将原文与命中区间拆分为可渲染的片段，并让重叠区间保留最高风险项。
export function segmentText(text: string, spans: HighlightSpan[]): Segment[] {
  if (!spans || spans.length === 0) return [{ text }];
  const offsets = codePointOffsets(text);
  const codePointLength = offsets.length - 1;
  const candidates = spans.map((hit) => {
    const startCodePoint = Math.max(0, Math.min(hit.start_index, codePointLength));
    const endCodePoint = Math.max(startCodePoint, Math.min(hit.end_index, codePointLength));
    return {
      hit,
      start: offsets[startCodePoint],
      end: offsets[endCodePoint],
    };
  }).filter((item) => item.end > item.start);

  const selected: typeof candidates = [];
  for (const candidate of candidates.sort((a, b) =>
    (RISK_PRIORITY[b.hit.risk_level || "none"] || 0) - (RISK_PRIORITY[a.hit.risk_level || "none"] || 0)
    || (b.end - b.start) - (a.end - a.start)
    || a.start - b.start
  )) {
    const overlaps = selected.some((item) =>
      candidate.start < item.end && candidate.end > item.start
    );
    if (!overlaps) selected.push(candidate);
  }
  selected.sort((a, b) => a.start - b.start || a.end - b.end);

  const segs: Segment[] = [];
  let cursor = 0;
  for (const item of selected) {
    const { start: s, end: e, hit } = item;
    if (s > cursor) segs.push({ text: text.slice(cursor, s) });
    segs.push({ text: text.slice(s, e), hit });
    cursor = e;
  }
  if (cursor < text.length) segs.push({ text: text.slice(cursor) });
  return segs;
}
