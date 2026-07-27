import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { History as HistIcon, Trash2, Copy, RefreshCw, Edit3, Download, X, FileJson } from "lucide-react";
import { api } from "../api/client";
import type { HistoryRecord, ComplianceResult } from "../types";
import { RiskBadge } from "../components/RiskBadge";
import { ComplianceReport } from "../components/ComplianceReport";
import { riskMeta } from "../utils/risk";
import { copyText, downloadText } from "../utils/misc";

export default function History() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<HistoryRecord | null>(null);
  const [recheck, setRecheck] = useState<ComplianceResult | null>(null);
  const navigate = useNavigate();

  async function load() {
    setLoading(true);
    const r = await api.history(200);
    setLoading(false);
    if (r.success) setRecords(r.data);
  }
  useEffect(() => { load(); }, []);

  async function del(id: string) {
    if (!confirm("确定删除该记录？")) return;
    await api.deleteHistory(id);
    load();
  }
  async function clearAll() {
    if (!confirm("确定清空全部最近记录？此操作不可恢复。")) return;
    await api.clearHistory();
    load();
  }

  function continueEdit(rec: HistoryRecord) {
    sessionStorage.setItem("continue_input", JSON.stringify(rec.input || {}));
    navigate("/generate");
  }

  async function recheckRecord(rec: HistoryRecord) {
    const text = rec.detection?.input_text || rec.generated?.versions?.[0]?.text || rec.input?.text || "";
    const platform = rec.platform || "小红书";
    const content_type = rec.generated?.content_type || rec.detection?.content_type || "项目介绍";
    const r = await api.check({ text, platform, content_type, brand: rec.brand });
    if (r.success) setRecheck(r.data);
    else alert(r.message || "重新检测失败");
  }

  function exportJson(rec: HistoryRecord) {
    downloadText(`记录_${rec.id}.json`, JSON.stringify(rec, null, 2), "application/json");
  }
  function exportMd(rec: HistoryRecord) {
    const lines = [
      `# 记录 ${rec.id}`,
      `- 操作类型：${rec.operation_type}`,
      `- 品牌：${rec.brand || "—"}`,
      `- 平台：${rec.platform || "—"}`,
      `- 风险等级：${rec.risk_level || "—"}`,
      `- 创建时间：${rec.created_at || "—"}`,
      "",
      "## 输入",
      "```json",
      JSON.stringify(rec.input || {}, null, 2),
      "```",
    ];
    if (rec.generated) {
      lines.push("", "## 生成结果");
      rec.generated.versions.forEach((v) => lines.push(`\n### 版本 ${v.version_index}\n${v.text}`));
    }
    if (rec.detection) {
      lines.push("", "## 检测报告");
      lines.push("", rec.detection.review_summary || "");
    }
    downloadText(`记录_${rec.id}.md`, lines.join("\n"), "text/markdown");
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>最近记录</h2>
          <p style={{ margin: 0, color: "#6b7280", fontSize: 13 }}>仅用于找回此前内容，不记录用户身份与审核结果。</p>
        </div>
        <button className="btn btn-danger" onClick={clearAll}><Trash2 size={16} /> 清空全部</button>
      </div>

      {loading && <div style={{ color: "#6b7280" }}>加载中…</div>}
      {!loading && records.length === 0 && (
        <div className="card" style={{ color: "#9ca3af", textAlign: "center", padding: 40 }}>暂无记录</div>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {records.map((rec) => {
          const meta = riskMeta(rec.risk_level || "none");
          return (
            <div key={rec.id} className="card" style={{ padding: 12 }}>
              <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 12, background: "#eff6ff", color: "#1d4ed8", borderRadius: 6, padding: "2px 8px" }}>{rec.operation_type === "generation" ? "内容生成" : "合规检测"}</span>
                <span style={{ fontSize: 13 }}>{rec.brand || "—"} · {rec.platform || "—"}</span>
                <RiskBadge meta={meta} />
                <span style={{ fontSize: 12, color: "#9ca3af", marginLeft: "auto" }}>{rec.created_at}</span>
              </div>
              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 6, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {rec.detection?.input_text || rec.generated?.versions?.[0]?.text || JSON.stringify(rec.input).slice(0, 60)}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => setView(rec)}>查看</button>
                <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={async () => { const t = rec.detection?.input_text || rec.generated?.versions?.[0]?.text || ""; alert((await copyText(t)) ? "已复制" : "复制失败"); }}><Copy size={14} /> 复制</button>
                <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => continueEdit(rec)}><Edit3 size={14} /> 继续修改</button>
                <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => recheckRecord(rec)}><RefreshCw size={14} /> 重新检测</button>
                <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => exportJson(rec)}><FileJson size={14} /> JSON</button>
                <button className="btn" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => exportMd(rec)}><Download size={14} /> MD</button>
                <button className="btn btn-danger" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => del(rec.id)}><Trash2 size={14} /></button>
              </div>
            </div>
          );
        })}
      </div>

      {view && (
        <Modal title={`记录 ${view.id}`} onClose={() => setView(null)}>
          {view.generated && (
            <div style={{ display: "grid", gap: 14 }}>
              {view.generated.versions.map((v) => (
                <div key={v.version_index}>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>版本 {v.version_index}</div>
                  <div style={{ fontSize: 14, whiteSpace: "pre-wrap", background: "#f9fafb", borderRadius: 8, padding: 10, marginBottom: 8 }}>{v.text}</div>
                  <ComplianceReport result={v.compliance} />
                </div>
              ))}
            </div>
          )}
          {!view.generated && view.detection && <ComplianceReport result={view.detection} />}
          {!view.generated && !view.detection && <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(view.input, null, 2)}</pre>}
        </Modal>
      )}

      {recheck && (
        <Modal title="重新检测结果" onClose={() => setRecheck(null)}>
          <ComplianceReport result={recheck} />
        </Modal>
      )}
    </div>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16 }} onClick={onClose}>
      <div style={{ background: "#fff", borderRadius: 12, maxWidth: 760, width: "100%", maxHeight: "88vh", overflow: "auto", padding: 20 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>{title}</h3>
          <button className="btn" onClick={onClose}><X size={16} /> 关闭</button>
        </div>
        {children}
      </div>
    </div>
  );
}
