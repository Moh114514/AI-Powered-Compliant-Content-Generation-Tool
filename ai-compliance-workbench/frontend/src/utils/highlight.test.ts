import { describe, expect, it } from "vitest";
import type { HighlightSpan } from "../types";
import { segmentText } from "./highlight";

function codePointSpans(text: string, needle: string): HighlightSpan[] {
  const characters = Array.from(text);
  const needleLength = Array.from(needle).length;
  const spans: HighlightSpan[] = [];
  for (let index = 0; index <= characters.length - needleLength; index += 1) {
    if (characters.slice(index, index + needleLength).join("") !== needle) continue;
    spans.push({
      rule_id: "xhs-bw:BW0031",
      matched_text: needle,
      start_index: index,
      end_index: index + needleLength,
      matching_method: "xhs_banned_word",
      source_type: "xhs_banned_word",
      risk_level: "medium",
    });
  }
  return spans;
}

describe("segmentText", () => {
  it("converts Unicode codepoint offsets before slicing UTF-16 strings", () => {
    const text = "前🔥抗衰中👏🏻抗衰后😌抗衰再👩‍⚕️抗衰";
    const segments = segmentText(text, codePointSpans(text, "抗衰"));

    expect(segments.map((segment) => segment.text).join("")).toBe(text);
    expect(segments.filter((segment) => segment.hit).map((segment) => segment.text)).toEqual([
      "抗衰", "抗衰", "抗衰", "抗衰",
    ]);
  });

  it("keeps the highest-risk highlight when spans overlap", () => {
    const text = "零风险";
    const segments = segmentText(text, [
      {
        rule_id: "low",
        matched_text: "零风险",
        start_index: 0,
        end_index: 3,
        matching_method: "contains",
        risk_level: "low",
      },
      {
        rule_id: "critical",
        matched_text: "风险",
        start_index: 1,
        end_index: 3,
        matching_method: "contains",
        risk_level: "critical",
      },
    ]);

    expect(segments.map((segment) => segment.text).join("")).toBe(text);
    expect(segments.filter((segment) => segment.hit)).toHaveLength(1);
    expect(segments.find((segment) => segment.hit)?.hit?.rule_id).toBe("critical");
    expect(segments.find((segment) => segment.hit)?.text).toBe("风险");
  });
});
