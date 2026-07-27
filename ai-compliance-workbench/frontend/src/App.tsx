import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import ContentGeneration from "./pages/ContentGeneration";
import ComplianceCheck from "./pages/ComplianceCheck";
import History from "./pages/History";
import RuleBrowser from "./pages/RuleBrowser";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to="/generate" replace />} />
          <Route path="generate" element={<ContentGeneration />} />
          <Route path="check" element={<ComplianceCheck />} />
          <Route path="history" element={<History />} />
          <Route path="rules" element={<RuleBrowser />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/generate" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
