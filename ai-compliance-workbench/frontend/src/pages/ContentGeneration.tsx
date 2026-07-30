import React, { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Copy, FileText, Save, Sparkles, Square, Trash2, Wand2 } from "lucide-react";
import { api } from "../api/client";
import { ComplianceReport } from "../components/ComplianceReport";
import { OperationProgress } from "../components/OperationProgress";
import { RiskBadge } from "../components/RiskBadge";
import { useElapsedSeconds } from "../hooks/useElapsedSeconds";
import type { Brand, GenerateResult, VersionResult } from "../types";
import { copyText, downloadText } from "../utils/misc";
import { statusOf } from "../utils/risk";

const DEMO = {
  brand: "光年拾捌",
  platform: "小红书",
  content_type: "项目介绍",
  topic: "夏季光电抗衰体验周",
  selling_points: "全城效果最好，零风险，7天年轻十岁，限时免费体验",
  target_audience: "25-40岁关注抗初老的都市女性",
  campaign_info: "7月活动，具体条件以正式活动说明为准",
  tone: "亲切专业",
  length: "中",
  extra_requirements: "",
  use_brand_profile: true,
  versions: 3,
};

type BusyAction = "generate" | `adjust-${number}` | `rewrite-${number}` | "save" | null;
const GENERATION_DRAFT_KEY = "workbench:generation-draft:v1";

function loadGenerationDraft(): {
  form: typeof DEMO;
  result: GenerateResult | null;
  openVersions: Record<number, boolean>;
  restored: boolean;
} {
  const continuedRaw = sessionStorage.getItem("continue_input");
  if (continuedRaw) {
    sessionStorage.removeItem("continue_input");
    try {
      return {
        form: { ...DEMO, ...JSON.parse(continuedRaw) },
        result: null,
        openVersions: {},
        restored: true,
      };
    } catch {
      // Fall through to the regular draft.
    }
  }
  try {
    const saved = JSON.parse(sessionStorage.getItem(GENERATION_DRAFT_KEY) || "null");
    if (saved?.form) {
      return {
        form: { ...DEMO, ...saved.form },
        result: saved.result || null,
        openVersions: saved.openVersions || {},
        restored: true,
      };
    }
  } catch {
    // Ignore corrupt browser state.
  }
  return { form: { ...DEMO }, result: null, openVersions: {}, restored: false };
}

export default function ContentGeneration() {
  const initialDraft = useRef(loadGenerationDraft()).current;
  const [brands, setBrands] = useState<Brand[]>([]);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [contentTypes, setContentTypes] = useState<Record<string, string[]>>({});
  const [form, setForm] = useState(initialDraft.form);
  const [result, setResult] = useState<GenerateResult | null>(initialDraft.result);
  const [openVersions, setOpenVersions] = useState<Record<number, boolean>>(initialDraft.openVersions);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rewriteModal, setRewriteModal] = useState<{ text: string; rev: any } | null>(null);
  const generationController = useRef<AbortController | null>(null);
  const generating = busy === "generate";
  const elapsedSeconds = useElapsedSeconds(generating);

  useEffect(() => {
    async function initialize() {
      const [brandResponse, platformResponse, typeResponse, settingsResponse] = await Promise.all([
        api.brands(), api.platforms(), api.contentTypes(), api.settings(),
      ]);
      if (brandResponse.success) setBrands(brandResponse.data);
      if (platformResponse.success) setPlatforms(platformResponse.data);
      if (typeResponse.success) setContentTypes(typeResponse.data);
      const firstError = [brandResponse, platformResponse, typeResponse, settingsResponse].find((response) => !response.success);
      if (firstError && !firstError.success) setError(firstError.message);

      if (initialDraft.restored) return;
      setForm((current) => {
        const settings = settingsResponse.success ? settingsResponse.data : {};
        const configuredBrand = settings.default_brand || current.brand;
        const knownBrand = brandResponse.success
          ? brandResponse.data.find((item) => item.brand_id === configuredBrand || item.brand_name === configuredBrand)
          : undefined;
        return {
          ...current,
          brand: knownBrand?.brand_name || configuredBrand,
          platform: settings.default_platform || current.platform,
          versions: settings.default_versions || current.versions,
          tone: settings.default_tone || current.tone,
          length: settings.default_length || current.length,
        };
      });
    }
    void initialize();
  }, []);

  useEffect(() => () => generationController.current?.abort(), []);

  useEffect(() => {
    try {
      sessionStorage.setItem(GENERATION_DRAFT_KEY, JSON.stringify({ form, result, openVersions }));
    } catch {
      // A full compliance report can exceed a browser storage quota; keep the UI usable.
    }
  }, [form, result, openVersions]);

  const contentTypeOptions = useMemo(() => contentTypes[form.platform] || [], [contentTypes, form.platform]);

  useEffect(() => {
    if (contentTypeOptions.length && !contentTypeOptions.includes(form.content_type)) {
      setForm((current) => ({ ...current, content_type: contentTypeOptions[0] }));
    }
  }, [contentTypeOptions, form.content_type]);

  function setField<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setNotice(null);
  }

  function changePlatform(platform: string) {
    const firstType = contentTypes[platform]?.[0] || "";
    setForm((current) => ({ ...current, platform, content_type: firstType }));
    setResult(null);
  }

  async function onGenerate() {
    if (!form.topic.trim() && !form.selling_points.trim()) {
      setError("请至少填写主题或核心卖点");
      return;
    }
    setBusy("generate");
    setError(null);
    setNotice(null);
    const controller = new AbortController();
    generationController.current = controller;
    const response = await api.generate(form, controller.signal);
    if (generationController.current === controller) {
      generationController.current = null;
      setBusy(null);
    }
    if (!response.success) {
      if (response.error_code === "REQUEST_CANCELLED") {
        setNotice("已停止本次生成与检测，原有内容未被覆盖。");
        return;
      }
      setError(response.message || "生成失败");
      return;
    }
    setResult(response.data);
    setOpenVersions({});
    const messages: string[] = [];
    if (response.data.history_saved) messages.push("已自动保存到最近记录");
    if (response.data.history_error) setError(response.data.history_error);
    if ((response.data.returned_versions ?? response.data.versions.length) < (response.data.requested_versions ?? form.versions)) {
      messages.push("模型返回的有效版本少于请求数量，系统已保留实际可用版本");
    }
    if (response.data.timings_ms) {
      messages.push(
        `耗时：模型生成 ${(response.data.timings_ms.model_generation / 1000).toFixed(1)} 秒，合规检测 ${(response.data.timings_ms.compliance_all_versions / 1000).toFixed(1)} 秒`,
      );
    }
    if (messages.length) setNotice(messages.join("；") + "。");
  }

  function stopGeneration() {
    generationController.current?.abort();
  }

  function onClear() {
    const firstType = contentTypes[form.platform]?.[0] || DEMO.content_type;
    setForm({ ...DEMO, brand: form.brand, platform: form.platform, content_type: firstType });
    setResult(null);
    setError(null);
    setNotice(null);
  }

  async function onSaveHistory() {
    if (!result) return;
    setBusy("save");
    const response = await api.addHistory({
      operation_type: "generation",
      brand: form.brand,
      platform: form.platform,
      input: form,
      generated: result,
      detection: null,
      risk_level: result.versions[0]?.overall_risk_level || "none",
    });
    setBusy(null);
    if (response.success) setNotice("已将当前版本另存到最近记录");
    else setError(response.message);
  }

  function updateVersion(index: number, patch: Partial<VersionResult>) {
    setResult((current) => {
      if (!current) return current;
      return { ...current, versions: current.versions.map((version, position) => position === index ? { ...version, ...patch } : version) };
    });
  }

  async function doAdjust(index: number, adjustType: "缩短" | "扩写" | "调整语气") {
    const version = result?.versions[index];
    if (!version) return;
    setBusy(`adjust-${index}`);
    setError(null);
    const response = await api.adjust({
      text: version.text,
      platform: version.platform,
      content_type: version.content_type,
      platform_id: version.platform_id,
      scene_id: version.scene_id,
      brand: form.brand,
      adjust_type: adjustType,
      tone: form.tone,
    });
    setBusy(null);
    if (!response.success) {
      setError(response.message || "调整失败");
      return;
    }
    const compliance = response.data.compliance;
    updateVersion(index, {
      text: response.data.text,
      char_count: response.data.text.length,
      compliance,
      overall_risk_level: compliance.overall_risk_level,
      matched_count: compliance.stats?.unique_risk_count
        ?? compliance.matched_rules.length
          + (compliance.banned_word_hits?.length ?? 0)
          + (compliance.semantic_findings?.length ?? 0),
      manual_review_required: compliance.manual_review_required,
    });
    setNotice(`已基于当前版本完成${adjustType}，未混入原始表单中的主题或活动信息。`);
  }

  async function doRewrite(index: number) {
    const version = result?.versions[index];
    if (!version) return;
    setBusy(`rewrite-${index}`);
    setError(null);
    const response = await api.rewrite({
      text: version.text,
      platform: version.platform,
      content_type: version.content_type,
      platform_id: version.platform_id,
      scene_id: version.scene_id,
      brand: form.brand,
    });
    setBusy(null);
    if (response.success) setRewriteModal({ text: version.text, rev: response.data });
    else setError(response.message || "改写失败");
  }

  async function downloadReport(version: VersionResult) {
    const response = await api.report(version.compliance, "md");
    if (response.success) downloadText(`检测报告_${version.platform}_v${version.version_index}.md`, response.data.content, "text/markdown");
    else setError(response.message);
  }

  return <div>
    <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>内容生成</h2>
    <p style={{ margin: "0 0 16px", color: "#6b7280", fontSize: 13 }}>选择品牌和发布场景，生成文案后自动进行确定性与语义风险检测。</p>
    {error && <Message tone="error">⚠️ {error}</Message>}
    {notice && <Message tone="success">{notice}</Message>}
    {generating && <OperationProgress label="系统正在生成文案并执行合规检测" elapsedSeconds={elapsedSeconds} />}

    <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 420px) 1fr", gap: 16, alignItems: "start" }} className="gen-grid">
      <div className="card"><div style={{ display: "grid", gap: 10 }}>
        <Field label="品牌" hint="可选择已有品牌，也可直接输入名称">
          <input className="input" list="generation-brand-options" maxLength={100} value={form.brand} onChange={(event) => setField("brand", event.target.value)} placeholder="请输入品牌名称" />
          <datalist id="generation-brand-options">{brands.map((brand) => <option key={brand.brand_id} value={brand.brand_name}>{brand.is_demo ? "演示品牌" : "已有品牌"}</option>)}</datalist>
        </Field>
        <Field label="发布平台"><select className="select" value={form.platform} onChange={(event) => changePlatform(event.target.value)}>{platforms.map((platform) => <option key={platform}>{platform}</option>)}</select></Field>
        <Field label="内容类型"><select className="select" value={form.content_type} onChange={(event) => setField("content_type", event.target.value)}>{contentTypeOptions.map((type) => <option key={type}>{type}</option>)}</select></Field>
        <Field label="主题" hint="主题和核心卖点至少填写一项"><input className="input" maxLength={300} value={form.topic} onChange={(event) => setField("topic", event.target.value)} placeholder="例如：夏季光电抗衰体验周" /></Field>
        <Field label="主要内容要点" hint={`${form.selling_points.length}/3000`}><textarea className="textarea" maxLength={3000} value={form.selling_points} onChange={(event) => setField("selling_points", event.target.value)} placeholder="请填写真实、可核验的信息，系统会识别高风险表达" /></Field>
        <Field label="目标人群"><input className="input" maxLength={500} value={form.target_audience} onChange={(event) => setField("target_audience", event.target.value)} /></Field>
        <Field label="活动信息"><input className="input" maxLength={1000} value={form.campaign_info} onChange={(event) => setField("campaign_info", event.target.value)} /></Field>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <Field label="语气风格"><input className="input" value={form.tone} onChange={(event) => setField("tone", event.target.value)} /></Field>
          <Field label="内容长度"><select className="select" value={form.length} onChange={(event) => setField("length", event.target.value)}>{["短", "中", "长"].map((length) => <option key={length}>{length}</option>)}</select></Field>
        </div>
        <Field label="补充要求"><input className="input" maxLength={2000} value={form.extra_requirements} onChange={(event) => setField("extra_requirements", event.target.value)} /></Field>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}><input type="checkbox" checked={form.use_brand_profile} onChange={(event) => setField("use_brand_profile", event.target.checked)} />使用品牌资料（偏好用词和禁用词）</label>
        <Field label="生成版本数量"><select className="select" value={form.versions} onChange={(event) => setField("versions", Number(event.target.value))}>{[1, 2, 3, 4, 5].map((number) => <option key={number} value={number}>{number} 个</option>)}</select></Field>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 4 }}>
          <button className="btn btn-primary" onClick={onGenerate} disabled={busy !== null}><Sparkles size={16} /> {busy === "generate" ? "生成与检测中…" : "生成并检测"}</button>
          {generating && <button className="btn btn-danger" onClick={stopGeneration}><Square size={15} /> 停止</button>}
          <button className="btn" onClick={() => { setForm({ ...DEMO }); setResult(null); }} disabled={busy !== null}><FileText size={16} /> 加载风险示例</button>
          <button className="btn" onClick={onClear} disabled={busy !== null}><Trash2 size={16} /> 清空</button>
          <button className="btn" onClick={onSaveHistory} disabled={!result || busy !== null}><Save size={16} /> {busy === "save" ? "保存中…" : result?.history_saved ? "另存当前版本" : "保存到最近记录"}</button>
        </div>
      </div></div>

      <div>
        {!result && <div className="card" style={{ color: "#9ca3af", textAlign: "center", padding: 40, fontSize: 14 }}>填写左侧信息后点击「生成并检测」。</div>}
        {result && <div style={{ display: "grid", gap: 14 }}>
          {result.demo_mode && <Message tone="warning">当前为演示模式，生成内容不代表真实品牌资料；关键词、正则和模拟语义检测仍会运行。</Message>}
          {result.versions.map((version, index) => {
            const meta = statusOf(version.compliance);
            const open = openVersions[version.version_index];
            const itemBusy = busy === `adjust-${index}` || busy === `rewrite-${index}`;
            return <div key={version.version_index} className="card">
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginBottom: 8 }}><b style={{ fontSize: 14 }}>版本 {version.version_index}</b><RiskBadge meta={meta} /><span style={{ fontSize: 12, color: "#6b7280" }}>{version.platform} · {version.content_type} · {version.char_count} 字 · {version.model} · 命中 {version.matched_count}</span></div>
              <div style={{ fontSize: 14, whiteSpace: "pre-wrap", lineHeight: 1.7, background: "#f9fafb", border: "1px solid #f1f5f9", borderRadius: 8, padding: 10 }}>{version.text}</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                <SmallButton onClick={async () => setNotice((await copyText(version.text)) ? "已复制文案" : "复制失败")}><Copy size={14} />复制文案</SmallButton>
                <SmallButton disabled={busy !== null} onClick={() => doAdjust(index, "缩短")}>缩短</SmallButton>
                <SmallButton disabled={busy !== null} onClick={() => doAdjust(index, "扩写")}>扩写</SmallButton>
                <SmallButton disabled={busy !== null} onClick={() => doAdjust(index, "调整语气")}>调整语气</SmallButton>
                <SmallButton disabled={busy !== null} onClick={() => doRewrite(index)}><Wand2 size={14} />{itemBusy ? "处理中…" : "一键合规改写"}</SmallButton>
                <SmallButton onClick={() => setOpenVersions((current) => ({ ...current, [version.version_index]: !current[version.version_index] }))}><ChevronDown size={14} />{open ? "收起风险" : "查看风险"}</SmallButton>
                <SmallButton onClick={async () => setNotice((await copyText(version.compliance.review_summary)) ? "已复制复核摘要" : "复制失败")}><Copy size={14} />复制复核摘要</SmallButton>
                <SmallButton onClick={() => downloadReport(version)}><FileText size={14} />下载检测报告</SmallButton>
              </div>
              {open && <div style={{ marginTop: 10 }}><ComplianceReport result={version.compliance} /></div>}
            </div>;
          })}
        </div>}
      </div>
    </div>

    {rewriteModal && <RewriteModal text={rewriteModal.text} rev={rewriteModal.rev} onClose={() => setRewriteModal(null)} />}
  </div>;
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) { return <div><div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{label}{hint && <span style={{ color: "#9ca3af", fontWeight: 400, marginLeft: 6 }}>{hint}</span>}</div>{children}</div>; }
function SmallButton({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) { return <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} {...props}>{children}</button>; }
function Message({ tone, children }: { tone: "error" | "success" | "warning"; children: React.ReactNode }) { const styles = tone === "error" ? ["#fef2f2", "#fecaca", "#b91c1c"] : tone === "success" ? ["#f0fdf4", "#bbf7d0", "#166534"] : ["#fffbeb", "#fde68a", "#92400e"]; return <div style={{ background: styles[0], border: `1px solid ${styles[1]}`, color: styles[2], borderRadius: 8, padding: "8px 10px", fontSize: 13, marginBottom: 12 }}>{children}</div>; }

function RewriteModal({ text, rev, onClose }: { text: string; rev: any; onClose: () => void }) {
  const revisedCompliance = rev.revised_compliance;
  return <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }}>
    <div style={{ background: "#fff", borderRadius: 12, maxWidth: 720, width: "100%", maxHeight: "88vh", overflow: "auto", padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}><h3 style={{ margin: 0, fontSize: 16 }}>一键合规改写</h3><button className="btn" onClick={onClose}>关闭</button></div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>原文</div><div style={{ fontSize: 14, whiteSpace: "pre-wrap", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: 10, marginBottom: 12 }}>{text}</div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 6 }}>建议修改稿</div><div style={{ fontSize: 14, whiteSpace: "pre-wrap", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 10, marginBottom: 12 }}>{rev.suggested_revision || "（无可自动生成的改写稿，需人工复核）"}</div>
      {revisedCompliance && <div style={{ marginBottom: 12 }}><b style={{ fontSize: 13 }}>改写后复检：</b> {revisedCompliance.overall_risk_level}，命中 {revisedCompliance.stats?.unique_risk_count ?? (revisedCompliance.matched_rules?.length ?? 0) + (revisedCompliance.banned_word_hits?.length ?? 0) + (revisedCompliance.semantic_findings?.length ?? 0)} 项风险{revisedCompliance.manual_review_required ? "，仍需人工复核" : ""}。</div>}
      {!!rev.unresolved_items?.length && <div style={{ fontSize: 13, color: "#6d28d9", marginBottom: 12 }}>仍需处理：{rev.unresolved_items.join("；")}</div>}
      <div style={{ display: "flex", gap: 8 }}><button className="btn btn-primary" disabled={!rev.suggested_revision} onClick={async () => alert((await copyText(rev.suggested_revision || "")) ? "已复制" : "复制失败")}><Copy size={14} />复制修改稿</button><button className="btn" disabled={!rev.suggested_revision} onClick={() => downloadText("合规改写稿.txt", rev.suggested_revision || "", "text/plain")}>下载 TXT</button></div>
    </div>
  </div>;
}
