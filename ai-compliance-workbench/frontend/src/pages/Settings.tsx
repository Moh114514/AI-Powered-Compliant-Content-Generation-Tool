import React, { useEffect, useState } from "react";
import { Settings as Cog, RefreshCw, CheckCircle, AlertTriangle, Trash2, Save } from "lucide-react";
import { api } from "../api/client";
import type { Settings as SettingsType, StatusInfo } from "../types";

export default function Settings() {
  const [settings, setSettings] = useState<SettingsType>({});
  const [status, setStatus] = useState<StatusInfo | null>(null);
  const [saved, setSaved] = useState(false);
  const [validResult, setValidResult] = useState<any>(null);

  useEffect(() => {
    api.settings().then((r) => r.success && setSettings(r.data));
    api.status().then((r) => r.success && setStatus(r.data));
  }, []);

  function set<K extends keyof SettingsType>(k: K, v: any) {
    setSettings((s) => ({ ...s, [k]: v }));
    setSaved(false);
  }

  async function save() {
    const r = await api.patchSettings(settings);
    if (r.success) {
      setSettings(r.data);
      setSaved(true);
    } else {
      alert(r.message || "保存失败");
    }
  }

  async function reload() {
    const r = await api.reloadRules();
    if (r.success) {
      setStatus((s) => (s ? { ...s, ...r.data } : s));
      alert("规则库已重新加载");
    }
  }
  async function validate() {
    const r = await api.validateRules();
    if (r.success) setValidResult(r.data);
  }

  return (
    <div>
      <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>工具设置</h2>
      <p style={{ margin: "0 0 16px", color: "#6b7280", fontSize: 13 }}>仅配置与工具运行直接相关的内容。</p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }} className="set-grid">
        {/* 模型配置 */}
        <Section title="模型配置">
          <Field label="Provider">
            <select className="select" value={settings.model_provider || "mock"} onChange={(e) => set("model_provider", e.target.value)}>
              <option value="mock">Mock（演示模式，无需 API Key）</option>
              <option value="openai_compatible">OpenAI 兼容（DeepSeek / 通义 等）</option>
            </select>
          </Field>
          {settings.model_provider !== "mock" && (
            <>
              <Field label="模型名称">
                <input className="input" value={settings.model_name || ""} onChange={(e) => set("model_name", e.target.value)} />
              </Field>
              <Field label="API Base URL">
                <input className="input" value={settings.api_base || ""} onChange={(e) => set("api_base", e.target.value)} />
              </Field>
            </>
          )}
          <Field label="温度 (temperature)">
            <input type="number" step="0.1" className="input" value={settings.temperature ?? 0.7} onChange={(e) => set("temperature", Number(e.target.value))} />
          </Field>
          <Field label="最大 Token (max_tokens)">
            <input type="number" className="input" value={settings.max_tokens ?? 1200} onChange={(e) => set("max_tokens", Number(e.target.value))} />
          </Field>
          <div style={{ fontSize: 12, color: "#9ca3af", background: "#f9fafb", padding: 8, borderRadius: 8 }}>
            API Key 仅在项目根目录 <code>.env</code> 中配置（LLM_API_KEY），不在页面明文展示或存储。
          </div>
        </Section>

        {/* 生成设置 */}
        <Section title="生成设置">
          <Field label="默认品牌">
            <input className="input" value={settings.default_brand || ""} onChange={(e) => set("default_brand", e.target.value)} />
          </Field>
          <Field label="默认平台">
            <input className="input" value={settings.default_platform || ""} onChange={(e) => set("default_platform", e.target.value)} />
          </Field>
          <Field label="默认生成版本数">
            <input type="number" className="input" value={settings.default_versions ?? 3} onChange={(e) => set("default_versions", Number(e.target.value))} />
          </Field>
          <Field label="默认语气">
            <input className="input" value={settings.default_tone || ""} onChange={(e) => set("default_tone", e.target.value)} />
          </Field>
          <Field label="默认长度">
            <select className="select" value={settings.default_length || "中"} onChange={(e) => set("default_length", e.target.value)}>
              {["短", "中", "长"].map((l) => (<option key={l} value={l}>{l}</option>))}
            </select>
          </Field>
          <Toggle label="自动进行语义检测" value={!!settings.auto_semantic_check} onChange={(v) => set("auto_semantic_check", v)} />
        </Section>

        {/* 合规设置 */}
        <Section title="合规设置">
          <Toggle label="启用关键词检测" value={!!settings.enable_keyword_detection} onChange={(v) => set("enable_keyword_detection", v)} />
          <Toggle label="启用正则检测" value={!!settings.enable_regex_detection} onChange={(v) => set("enable_regex_detection", v)} />
          <Toggle label="启用语义检测" value={!!settings.enable_semantic_detection} onChange={(v) => set("enable_semantic_detection", v)} />
          <Toggle label="自动生成修改稿" value={!!settings.auto_generate_revision} onChange={(v) => set("auto_generate_revision", v)} />
          <Toggle label="强制显示免责声明" value={!!settings.force_disclaimer} onChange={(v) => set("force_disclaimer", v)} />
        </Section>

        {/* 记录设置 */}
        <Section title="记录设置">
          <Toggle label="保存最近记录" value={!!settings.save_history} onChange={(v) => set("save_history", v)} />
          <Field label="最大记录数量">
            <input type="number" className="input" value={settings.max_history ?? 100} onChange={(e) => set("max_history", Number(e.target.value))} />
          </Field>
          <Field label="数据保留天数">
            <input type="number" className="input" value={settings.history_retention_days ?? 90} onChange={(e) => set("history_retention_days", Number(e.target.value))} />
          </Field>
          <button className="btn btn-danger" onClick={async () => { if (confirm("确定清空全部最近记录？")) { await api.clearHistory(); alert("已清空"); } }}><Trash2 size={16} /> 清空记录</button>
        </Section>
      </div>

      {/* 数据状态 */}
      <Section title="数据状态" style={{ marginTop: 16 }}>
        {status && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 13 }}>
            <Info label="规则库版本" value={status.data_version} />
            <Info label="核心规则" value={`${status.rule_count} 条`} />
            <Info label="表达变体" value={`${status.variant_count} 条`} />
            <Info label="语义规则" value={`${status.semantic_count} 条`} />
            <Info label="来源数量" value={`${status.source_count} 条`} />
            <Info label="最近加载" value={status.loaded_at || "—"} />
            <Info label="数据校验" value={status.validation_valid ? "通过" : `异常(${status.validation_error_count})`} />
            <Info label="模式" value={status.demo_mode ? "演示模式" : "模型已连接"} />
          </div>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button className="btn" onClick={reload}><RefreshCw size={16} /> 重新加载规则库</button>
          <button className="btn" onClick={validate}><CheckCircle size={16} /> 运行数据校验</button>
        </div>
        {validResult && (
          <div style={{ marginTop: 10, fontSize: 13, background: validResult.valid ? "#f0fdf4" : "#fef2f2", border: `1px solid ${validResult.valid ? "#bbf7d0" : "#fecaca"}`, borderRadius: 8, padding: 10 }}>
            {validResult.valid ? "✅ 校验通过" : `⚠️ 发现 ${validResult.error_count} 个错误`}
            {validResult.errors?.length > 0 && (
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                {validResult.errors.map((e: string, i: number) => (<li key={i}>{e}</li>))}
              </ul>
            )}
          </div>
        )}
      </Section>

      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn btn-primary" onClick={save}><Save size={16} /> 保存设置</button>
        {saved && <span style={{ color: "#16a34a", fontSize: 13 }}>✅ 已保存</span>}
      </div>
    </div>
  );
}

function Section({ title, children, style }: { title: string; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div className="card" style={style}>
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>{title}</div>
      <div style={{ display: "grid", gap: 10 }}>{children}</div>
    </div>
  );
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (<div><div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{label}</div>{children}</div>);
}
function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 13 }}>
      <span>{label}</span>
      <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}
function Info({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #f1f5f9", paddingBottom: 4 }}>
      <span style={{ color: "#6b7280" }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}
