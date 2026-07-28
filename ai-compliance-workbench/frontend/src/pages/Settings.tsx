import React, { useEffect, useState } from "react";
import { CheckCircle, PlayCircle, RefreshCw, Save, Trash2 } from "lucide-react";
import { api } from "../api/client";
import { PromptCatalogManager } from "../components/PromptCatalogManager";
import type { Settings as SettingsType, StatusInfo, TestSuiteResult } from "../types";

export default function Settings() {
  const [settings, setSettings] = useState<SettingsType>({});
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [saved, setSaved] = useState(false);
  const [validResult, setValidResult] = useState<any>(null);
  const [testResult, setTestResult] = useState<TestSuiteResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    const [settingsResponse, statusResponse] = await Promise.all([api.settings(), api.status()]);
    if (settingsResponse.success) setSettings(settingsResponse.data);
    else setError(settingsResponse.message);
    if (statusResponse.success) setStatus(statusResponse.data);
    else setError((current) => current || statusResponse.message);
  }

  useEffect(() => { void load(); }, []);

  function set<K extends keyof SettingsType>(key: K, value: SettingsType[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  async function save() {
    setBusy("save");
    setError(null);
    const response = await api.patchSettings(settings);
    setBusy(null);
    if (response.success) {
      setSettings(response.data);
      setSaved(true);
      await load();
      window.dispatchEvent(new Event("workbench:status-changed"));
    } else setError(response.message);
  }

  async function reloadRules() {
    setBusy("reload");
    setError(null);
    const response = await api.reloadRules();
    setBusy(null);
    if (!response.success) {
      setError(response.message);
      return;
    }
    await load();
  }

  async function validate() {
    setBusy("validate");
    setError(null);
    const response = await api.validateRules();
    setBusy(null);
    if (response.success) setValidResult(response.data);
    else setError(response.message);
  }

  async function runTests() {
    setBusy("tests");
    setError(null);
    const response = await api.testSuite(undefined, false);
    setBusy(null);
    if (response.success) setTestResult(response.data);
    else setError(response.message);
  }

  return (
    <div>
      <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>工具设置</h2>
      <p style={{ margin: "0 0 16px", color: "#6b7280", fontSize: 13 }}>配置模型、检测能力、本地记录和规则库检查。</p>
      {error && <div className="card" style={{ marginBottom: 12, color: "#b91c1c", borderColor: "#fecaca", background: "#fef2f2" }}>⚠️ {error}</div>}
      {status?.default_platform_warning && <div className="card" style={{ marginBottom: 12, color: "#92400e", borderColor: "#fde68a", background: "#fffbeb" }}>{status.default_platform_warning}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }} className="set-grid">
        <Section title="模型配置">
          <Field label="Provider">
            <select className="select" value={settings.model_provider || "mock"} onChange={(event) => set("model_provider", event.target.value)}>
              <option value="mock">Mock（演示模式，无需 API Key）</option>
              <option value="openai_compatible">OpenAI 兼容接口</option>
            </select>
          </Field>
          {settings.model_provider !== "mock" && <>
            <Field label="模型名称"><input className="input" value={settings.model_name || ""} onChange={(event) => set("model_name", event.target.value)} /></Field>
            <Field label="API Base URL"><input className="input" value={settings.api_base || ""} onChange={(event) => set("api_base", event.target.value)} /></Field>
          </>}
          <Field label="温度（0—2）"><input type="number" min={0} max={2} step="0.1" className="input" value={settings.temperature ?? 0.7} onChange={(event) => set("temperature", Number(event.target.value))} /></Field>
          <Field label="最大 Token"><input type="number" min={128} max={32000} className="input" value={settings.max_tokens ?? 1200} onChange={(event) => set("max_tokens", Number(event.target.value))} /></Field>
          <Note>API Key 仅通过项目根目录 <code>.env</code> 中的 <code>LLM_API_KEY</code> 配置，不在网页保存。</Note>
          {settings.model_provider !== "mock" && status && (
            <Note>
              当前状态：{status.provider_ready
                ? `真实模型已就绪（${status.model_name || settings.model_name || "未命名模型"}）`
                : status.provider_error || "真实模型尚未就绪"}
            </Note>
          )}
        </Section>

        <Section title="生成设置">
          <Field label="默认品牌"><input className="input" value={settings.default_brand || ""} onChange={(event) => set("default_brand", event.target.value)} /></Field>
          <Field label="默认平台">
            <select className="select" value={settings.default_platform || "小红书"} onChange={(event) => set("default_platform", event.target.value)}>
              {(status?.platforms || ["朋友圈", "微信社群", "小红书", "微信公众号", "客服话术"]).map((platform) => <option key={platform}>{platform}</option>)}
            </select>
          </Field>
          <Field label="默认生成版本数"><input type="number" min={1} max={5} className="input" value={settings.default_versions ?? 3} onChange={(event) => set("default_versions", Number(event.target.value))} /></Field>
          <Field label="默认语气"><input className="input" value={settings.default_tone || ""} onChange={(event) => set("default_tone", event.target.value)} /></Field>
          <Field label="默认长度">
            <select className="select" value={settings.default_length || "中"} onChange={(event) => set("default_length", event.target.value)}>
              {(["短", "中", "长"] as const).map((length) => <option key={length}>{length}</option>)}
            </select>
          </Field>
          <Toggle label="生成后自动进行语义检测" value={!!settings.auto_semantic_check} onChange={(value) => set("auto_semantic_check", value)} />
        </Section>

        <Section title="合规设置">
          <Toggle label="启用关键词检测" value={!!settings.enable_keyword_detection} onChange={(value) => set("enable_keyword_detection", value)} />
          <Toggle label="启用正则检测" value={!!settings.enable_regex_detection} onChange={(value) => set("enable_regex_detection", value)} />
          <Toggle label="启用语义检测" value={!!settings.enable_semantic_detection} onChange={(value) => set("enable_semantic_detection", value)} />
          <Toggle label="检测时自动生成修改稿" value={!!settings.auto_generate_revision} onChange={(value) => set("auto_generate_revision", value)} />
          <Toggle label="强制显示免责声明" value={!!settings.force_disclaimer} onChange={(value) => set("force_disclaimer", value)} />
          <Note>建议关闭“检测时自动生成修改稿”，需要改写时再点击“一键合规改写”，可减少模型调用和等待时间。</Note>
        </Section>

        <Section title="记录设置">
          <Toggle label="保存最近记录" value={!!settings.save_history} onChange={(value) => set("save_history", value)} />
          <Field label="最大记录数量"><input type="number" min={1} max={5000} className="input" value={settings.max_history ?? 100} onChange={(event) => set("max_history", Number(event.target.value))} /></Field>
          <Field label="数据保留天数"><input type="number" min={1} max={3650} className="input" value={settings.history_retention_days ?? 90} onChange={(event) => set("history_retention_days", Number(event.target.value))} /></Field>
          <button className="btn btn-danger" onClick={async () => { if (confirm("确定清空全部最近记录？此操作不可恢复。")) { const response = await api.clearHistory(); if (!response.success) setError(response.message); } }}><Trash2 size={16} /> 清空记录</button>
        </Section>
      </div>

      <PromptCatalogManager
        modelReady={!!status?.provider_ready && !status?.demo_mode}
        demoMode={!!status?.demo_mode}
      />

      <Section title="规则库状态" style={{ marginTop: 16 }}>
        {status ? <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 8, fontSize: 13 }}>
          <Info label="规则库版本" value={status.data_version || "—"} />
          <Info label="核心规则" value={`${status.rule_count} 条`} />
          <Info label="表达变体" value={`${status.variant_count} 条`} />
          <Info label="语义规则" value={`${status.semantic_count} 条`} />
          <Info label="来源" value={`${status.source_count} 条`} />
          <Info label="测试样本" value={`${status.test_case_count ?? 0} 条`} />
          <Info label="视觉检查项" value={`${status.visual_check_count ?? 0} 条`} />
          <Info label="待人工复核规则" value={`${status.pending_review_count ?? 0} 条`} />
          <Info label="校验" value={status.validation_valid ? `通过（${status.validation_warning_count ?? 0} 条警告）` : `异常（${status.validation_error_count}）`} />
          <Info label="运行模式" value={status.demo_mode ? "演示模式" : status.provider_ready === false ? "真实模型未就绪" : "真实模型已就绪"} />
          <Info label="当前模型" value={status.demo_mode ? "Mock" : status.model_name || "—"} />
          <Info label="提示词版本" value={status.prompt_version || "—"} />
          <Info label="平台 / 场景" value={`${status.prompt_platform_count ?? 0} / ${status.prompt_scene_count ?? 0}`} />
          <Info label="提示词覆盖" value={`${status.prompt_override_count ?? 0} 项`} />
          <Info label="最近加载" value={status.loaded_at || "—"} />
        </div> : <div style={{ color: "#6b7280" }}>正在读取状态……</div>}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
          <button className="btn" onClick={reloadRules} disabled={busy !== null}><RefreshCw size={16} /> {busy === "reload" ? "加载中…" : "重新加载规则库"}</button>
          <button className="btn" onClick={validate} disabled={busy !== null}><CheckCircle size={16} /> {busy === "validate" ? "校验中…" : "运行数据校验"}</button>
          <button className="btn" onClick={runTests} disabled={busy !== null}><PlayCircle size={16} /> {busy === "tests" ? "测试中…" : "运行 320 条回归测试"}</button>
        </div>
        {validResult && <ValidationBox result={validResult} />}
        {testResult && <TestSuiteBox result={testResult} />}
      </Section>

      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn btn-primary" onClick={save} disabled={busy !== null}><Save size={16} /> {busy === "save" ? "保存中…" : "保存设置"}</button>
        {saved && <span style={{ color: "#16a34a", fontSize: 13 }}>✅ 已保存</span>}
      </div>
    </div>
  );
}

function ValidationBox({ result }: { result: any }) {
  return <div style={{ marginTop: 10, fontSize: 13, background: result.valid ? "#f0fdf4" : "#fef2f2", border: `1px solid ${result.valid ? "#bbf7d0" : "#fecaca"}`, borderRadius: 8, padding: 10 }}>
    <b>{result.valid ? "✅ 结构校验通过" : `⚠️ 发现 ${result.error_count} 个错误`}</b>
    <div style={{ marginTop: 4, color: "#6b7280" }}>警告：{result.warning_count ?? 0} 条；规则：{result.rule_count ?? 0}；变体：{result.variant_count ?? 0}。</div>
    {!!result.errors?.length && <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{result.errors.map((item: string, index: number) => <li key={index}>{item}</li>)}</ul>}
  </div>;
}

function TestSuiteBox({ result }: { result: TestSuiteResult }) {
  const rate = `${(result.pass_rate * 100).toFixed(1)}%`;
  return <div style={{ marginTop: 10, fontSize: 13, background: result.failed === 0 ? "#f0fdf4" : "#fffbeb", border: `1px solid ${result.failed === 0 ? "#bbf7d0" : "#fde68a"}`, borderRadius: 8, padding: 10 }}>
    <b>回归测试：{result.passed}/{result.total} 通过（{rate}）</b>
    <div style={{ marginTop: 4, color: "#6b7280" }}>{result.note}</div>
    {result.failed > 0 && <details style={{ marginTop: 8 }}>
      <summary style={{ cursor: "pointer" }}>查看失败样本（展示 {result.details.length} 条）</summary>
      <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
        {result.details.slice(0, 30).map((item) => <div key={item.test_id} style={{ background: "#fff", border: "1px solid #f3f4f6", borderRadius: 6, padding: 8 }}>
          <b>{item.test_id}</b> · {item.platform}/{item.content_type} · {item.problems.join("、")}
          <div style={{ marginTop: 3, color: "#6b7280" }}>{item.input_text}</div>
          {!!item.missing_rule_ids?.length && <div style={{ color: "#b45309" }}>漏命中：{item.missing_rule_ids.join("、")}</div>}
        </div>)}
      </div>
    </details>}
  </div>;
}

function Section({ title, children, style }: { title: string; children: React.ReactNode; style?: React.CSSProperties }) {
  return <div className="card" style={style}><div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>{title}</div><div style={{ display: "grid", gap: 10 }}>{children}</div></div>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div><div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{label}</div>{children}</div>; }
function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) { return <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 13 }}><span>{label}</span><input type="checkbox" checked={value} onChange={(event) => onChange(event.target.checked)} /></label>; }
function Info({ label, value }: { label: string; value: string }) { return <div style={{ display: "flex", justifyContent: "space-between", gap: 12, borderBottom: "1px solid #f1f5f9", paddingBottom: 4 }}><span style={{ color: "#6b7280" }}>{label}</span><span style={{ fontWeight: 500, textAlign: "right" }}>{value}</span></div>; }
function Note({ children }: { children: React.ReactNode }) { return <div style={{ fontSize: 12, color: "#6b7280", background: "#f9fafb", padding: 8, borderRadius: 8 }}>{children}</div>; }
