import type { ApiResponse } from "../types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<ApiResponse<T>> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const msg = body?.message || `请求失败（HTTP ${res.status}）`;
    return { success: false, data: null, message: msg, request_id: "", error_code: body?.error_code };
  }
  return body as ApiResponse<T>;
}

export const api = {
  health: () => request("/health"),
  status: () => request<any>("/status"),

  brands: () => request<Brand[]>("/brands"),
  brand: (id: string) => request<Brand>(`/brands/${id}`),

  platforms: () => request<string[]>("/platforms"),
  contentTypes: () => request<Record<string, string[]>>("/content-types"),
  promptTemplates: () => request<any[]>("/prompt-templates"),

  generate: (payload: any) => request<GenerateResult>("/generation/generate", { method: "POST", body: JSON.stringify(payload) }),
  rewrite: (payload: any) => request<any>("/generation/rewrite", { method: "POST", body: JSON.stringify(payload) }),
  adjust: (payload: any) => request<any>("/generation/adjust", { method: "POST", body: JSON.stringify(payload) }),

  check: (payload: any) => request<ComplianceResult>("/compliance/check", { method: "POST", body: JSON.stringify(payload) }),
  rules: (params: Record<string, any>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.append(k, String(v));
    });
    return request<{ total: number; rules: any[] }>(`/compliance/rules?${qs.toString()}`);
  },
  ruleDetail: (id: string) => request<RuleDetail>(`/compliance/rules/${id}`),
  sourceDetail: (id: string) => request<SourceDetail>(`/compliance/sources/${id}`),
  reloadRules: () => request<any>("/compliance/reload", { method: "POST" }),
  validateRules: () => request<any>("/compliance/validate", { method: "POST" }),

  history: (limit = 100) => request<HistoryRecord[]>(`/history?limit=${limit}`),
  historyOne: (id: string) => request<HistoryRecord>(`/history/${id}`),
  addHistory: (payload: any) => request<any>("/history", { method: "POST", body: JSON.stringify(payload) }),
  deleteHistory: (id: string) => request<any>(`/history/${id}`, { method: "DELETE" }),
  clearHistory: () => request<any>("/history", { method: "DELETE" }),

  settings: () => request<Settings>("/settings"),
  patchSettings: (patch: any) => request<Settings>("/settings", { method: "PATCH", body: JSON.stringify({ patch }) }),

  reviewSummary: (result: any, format = "txt") =>
    request<{ format: string; content: string }>("/export/review-summary", { method: "POST", body: JSON.stringify({ result, format }) }),
  report: (result: any, format = "md") =>
    request<{ format: string; content: string }>("/export/report", { method: "POST", body: JSON.stringify({ result, format }) }),
};
