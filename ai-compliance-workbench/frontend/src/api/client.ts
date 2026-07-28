import type {
  ApiResponse,
  Brand,
  ComplianceResult,
  GenerateResult,
  HistoryRecord,
  PromptCatalog,
  PromptPlatform,
  PromptScene,
  RuleDetail,
  Settings,
  SourceDetail,
  TestSuiteResult,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
const DEFAULT_TIMEOUT_MS = 70_000;

function failure<T>(message: string, errorCode = "NETWORK_ERROR"): ApiResponse<T> {
  return { success: false, data: null, message, request_id: "", error_code: errorCode };
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<ApiResponse<T>> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = new Headers(init?.headers || {});
    if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(BASE + path, { ...init, headers, signal: controller.signal });
    const text = await response.text();
    let body: any = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        return failure<T>(`服务器返回了无法解析的数据（HTTP ${response.status}）`, "INVALID_RESPONSE");
      }
    }
    if (!response.ok) {
      return failure<T>(body?.message || `请求失败（HTTP ${response.status}）`, body?.error_code || "HTTP_ERROR");
    }
    if (!body || typeof body.success !== "boolean") {
      return failure<T>("服务器响应结构不完整", "INVALID_RESPONSE");
    }
    return body as ApiResponse<T>;
  } catch (error: any) {
    if (error?.name === "AbortError") return failure<T>("请求超时，请检查后端或模型服务是否正常", "REQUEST_TIMEOUT");
    return failure<T>(`无法连接到后端服务：${error?.message || "未知网络错误"}`);
  } finally {
    window.clearTimeout(timer);
  }
}

export const api = {
  health: () => request<any>("/health", undefined, 10_000),
  status: () => request<any>("/status", undefined, 10_000),

  brands: () => request<Brand[]>("/brands"),
  brand: (id: string) => request<Brand>(`/brands/${encodeURIComponent(id)}`),

  platforms: () => request<string[]>("/platforms"),
  contentTypes: () => request<Record<string, string[]>>("/content-types"),
  promptTemplates: () => request<any[]>("/prompt-templates"),
  promptCatalog: (includeInactive = true) => request<PromptCatalog>(`/prompt-catalog?include_inactive=${includeInactive}`),
  saveBasePrompt: (prompt_text: string) => request<PromptCatalog>("/prompt-templates/base", { method: "PUT", body: JSON.stringify({ prompt_text }) }),
  resetBasePrompt: () => request<PromptCatalog>("/prompt-templates/base", { method: "DELETE" }),
  resetBuiltinPrompts: () => request<PromptCatalog>("/prompt-templates/reset-builtins", { method: "DELETE" }),
  createPromptPlatform: (payload: any) => request<PromptPlatform>("/prompt-platforms", { method: "POST", body: JSON.stringify(payload) }),
  updatePromptPlatform: (id: string, payload: any) => request<PromptPlatform>(`/prompt-platforms/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) }),
  deactivatePromptPlatform: (id: string) => request<PromptPlatform>(`/prompt-platforms/${encodeURIComponent(id)}`, { method: "DELETE" }),
  activatePromptPlatform: (id: string) => request<PromptPlatform>(`/prompt-platforms/${encodeURIComponent(id)}/activate`, { method: "POST" }),
  resetPlatformPrompt: (id: string) => request<PromptPlatform>(`/prompt-platforms/${encodeURIComponent(id)}/prompt`, { method: "DELETE" }),
  createPromptScene: (platformId: string, payload: any) => request<PromptScene>(`/prompt-platforms/${encodeURIComponent(platformId)}/scenes`, { method: "POST", body: JSON.stringify(payload) }),
  updatePromptScene: (id: string, payload: any) => request<PromptScene>(`/prompt-scenes/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) }),
  deactivatePromptScene: (id: string) => request<PromptScene>(`/prompt-scenes/${encodeURIComponent(id)}`, { method: "DELETE" }),
  activatePromptScene: (id: string) => request<PromptScene>(`/prompt-scenes/${encodeURIComponent(id)}/activate`, { method: "POST" }),
  resetScenePrompt: (id: string) => request<PromptScene>(`/prompt-scenes/${encodeURIComponent(id)}/prompt`, { method: "DELETE" }),
  promptAiDraft: (payload: any) => request<{ draft: string; target_type: string; provider: string; model: string; saved: boolean }>("/prompt-templates/ai-draft", { method: "POST", body: JSON.stringify(payload) }, 120_000),

  generate: (payload: any) => request<GenerateResult>("/generation/generate", { method: "POST", body: JSON.stringify(payload) }, 120_000),
  rewrite: (payload: any) => request<any>("/generation/rewrite", { method: "POST", body: JSON.stringify(payload) }, 120_000),
  adjust: (payload: any) => request<any>("/generation/adjust", { method: "POST", body: JSON.stringify(payload) }, 120_000),

  check: (payload: any) => request<ComplianceResult>("/compliance/check", { method: "POST", body: JSON.stringify(payload) }, 120_000),
  rules: (params: Record<string, any>) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") query.append(key, String(value));
    });
    return request<{ total: number; offset: number; limit: number; rules: any[] }>(`/compliance/rules?${query.toString()}`);
  },
  ruleDetail: (id: string) => request<RuleDetail>(`/compliance/rules/${encodeURIComponent(id)}`),
  sourceDetail: (id: string) => request<SourceDetail>(`/compliance/sources/${encodeURIComponent(id)}`),
  reloadRules: () => request<any>("/compliance/reload", { method: "POST" }),
  validateRules: () => request<any>("/compliance/validate", { method: "POST" }),
  testSuite: (limit?: number, includePassed = false) => {
    const query = new URLSearchParams({ include_passed: String(includePassed) });
    if (limit) query.set("limit", String(limit));
    return request<TestSuiteResult>(`/compliance/test-suite?${query.toString()}`, { method: "POST" }, 180_000);
  },

  history: (limit = 100) => request<HistoryRecord[]>(`/history?limit=${limit}`),
  historyOne: (id: string) => request<HistoryRecord>(`/history/${encodeURIComponent(id)}`),
  addHistory: (payload: any) => request<any>("/history", { method: "POST", body: JSON.stringify(payload) }),
  deleteHistory: (id: string) => request<any>(`/history/${encodeURIComponent(id)}`, { method: "DELETE" }),
  clearHistory: () => request<any>("/history", { method: "DELETE" }),

  settings: () => request<Settings>("/settings"),
  patchSettings: (patch: any) => request<Settings>("/settings", { method: "PATCH", body: JSON.stringify({ patch }) }),

  reviewSummary: (result: any, format = "txt") =>
    request<{ format: string; content: string }>("/export/review-summary", { method: "POST", body: JSON.stringify({ result, format }) }),
  report: (result: any, format = "md") =>
    request<{ format: string; content: string }>("/export/report", { method: "POST", body: JSON.stringify({ result, format }) }),
};
