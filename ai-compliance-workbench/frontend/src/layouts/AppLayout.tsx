import React, { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { PenLine, ShieldCheck, History, BookOpen, Settings, Sparkles } from "lucide-react";
import { api } from "../api/client";
import type { StatusInfo } from "../types";

const NAV = [
  { to: "/generate", label: "内容生成", icon: PenLine },
  { to: "/check", label: "合规检测", icon: ShieldCheck },
  { to: "/history", label: "最近记录", icon: History },
  { to: "/rules", label: "规则查询", icon: BookOpen },
  { to: "/settings", label: "工具设置", icon: Settings },
];

export function AppLayout() {
  const [status, setStatus] = useState<StatusInfo | null>(null);

  useEffect(() => {
    api.status().then((r) => r.success && setStatus(r.data));
  }, []);

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* 侧边导航（桌面）/ 顶部导航（窄屏） */}
      <aside
        style={{
          width: 190,
          flexShrink: 0,
          background: "#fff",
          borderRight: "1px solid #e5e7eb",
          padding: "16px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
        className="wb-sidebar"
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 8px 12px" }}>
          <Sparkles size={20} color="#2563eb" />
          <div style={{ fontSize: 14, fontWeight: 700, lineHeight: 1.3 }}>
            AI医美内容
            <br />
            合规工作台
          </div>
        </div>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            className={({ isActive }) =>
              "wb-nav" + (isActive ? " wb-nav-active" : "")
            }
          >
            <n.icon size={16} />
            <span>{n.label}</span>
          </NavLink>
        ))}
        <div style={{ marginTop: "auto", fontSize: 11, color: "#9ca3af", padding: "8px" }}>
          {status ? (
            <>
              规则库 {status.data_version}
              <br />
              核心规则 {status.rule_count} 条
              {status.demo_mode ? (
                <span style={{ color: "#d97706" }}> · 演示模式</span>
              ) : (
                <span style={{ color: "#16a34a" }}> · 模型已连接</span>
              )}
            </>
          ) : (
            "加载中…"
          )}
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0, padding: 20, overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
