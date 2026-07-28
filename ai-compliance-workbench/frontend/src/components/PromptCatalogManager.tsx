import { useEffect, useMemo, useState } from "react";
import { Bot, Plus, RefreshCw, Save } from "lucide-react";
import { api } from "../api/client";
import type { PromptCatalog, PromptPlatform, PromptScene } from "../types";

type EditorTarget = "base" | "platform" | "scene";

const EMPTY_PLATFORM = {
  name: "", description: "", prompt_text: "", rule_profile: "通用", sort_order: 100,
};
const EMPTY_SCENE = {
  name: "", description: "", prompt_text: "", rule_content_type: "通用", sort_order: 100,
};

export function PromptCatalogManager({ modelReady, demoMode }: { modelReady: boolean; demoMode: boolean }) {
  const [catalog, setCatalog] = useState<PromptCatalog | null>(null);
  const [platformId, setPlatformId] = useState("");
  const [sceneId, setSceneId] = useState("");
  const [basePrompt, setBasePrompt] = useState("");
  const [platformDraft, setPlatformDraft] = useState<Partial<PromptPlatform>>({});
  const [sceneDraft, setSceneDraft] = useState<Partial<PromptScene>>({});
  const [newPlatform, setNewPlatform] = useState({ ...EMPTY_PLATFORM });
  const [newScene, setNewScene] = useState({ ...EMPTY_SCENE });
  const [requirements, setRequirements] = useState("");
  const [target, setTarget] = useState<EditorTarget>("scene");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const platform = useMemo(
    () => catalog?.platforms.find((item) => item.id === platformId) || null,
    [catalog, platformId],
  );
  const scene = useMemo(
    () => platform?.scenes.find((item) => item.id === sceneId) || null,
    [platform, sceneId],
  );

  async function load(preferredPlatform = platformId, preferredScene = sceneId) {
    const response = await api.promptCatalog(true);
    if (!response.success) {
      setError(response.message);
      return;
    }
    const next = response.data;
    setCatalog(next);
    setBasePrompt(next.base_prompt.effective);
    const selectedPlatform = next.platforms.find((item) => item.id === preferredPlatform) || next.platforms[0];
    setPlatformId(selectedPlatform?.id || "");
    const selectedScene = selectedPlatform?.scenes.find((item) => item.id === preferredScene) || selectedPlatform?.scenes[0];
    setSceneId(selectedScene?.id || "");
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (platform) setPlatformDraft({ ...platform, prompt_text: platform.effective_prompt });
    const selected = platform?.scenes.find((item) => item.id === sceneId) || platform?.scenes[0];
    if (selected && selected.id !== sceneId) setSceneId(selected.id);
    if (!selected) setSceneId("");
  }, [platformId, catalog]);
  useEffect(() => {
    if (scene) setSceneDraft({ ...scene, prompt_text: scene.effective_prompt });
  }, [sceneId, platformId, catalog]);

  function begin(action: string) {
    setBusy(action);
    setError("");
    setMessage("");
  }
  function finish(messageText = "") {
    setBusy("");
    setMessage(messageText);
  }

  async function saveCurrent() {
    begin("save");
    let response;
    if (target === "base") {
      response = await api.saveBasePrompt(basePrompt);
    } else if (target === "platform" && platform) {
      response = await api.updatePromptPlatform(platform.id, {
        name: platformDraft.name,
        description: platformDraft.description,
        prompt_text: platformDraft.prompt_text,
        rule_profile: platformDraft.rule_profile,
        sort_order: platformDraft.sort_order,
      });
    } else if (target === "scene" && scene) {
      response = await api.updatePromptScene(scene.id, {
        name: sceneDraft.name,
        description: sceneDraft.description,
        prompt_text: sceneDraft.prompt_text,
        rule_content_type: sceneDraft.rule_content_type,
        sort_order: sceneDraft.sort_order,
      });
    } else {
      setBusy("");
      setError("请先选择要保存的提示词层级。");
      return;
    }
    if (!response.success) {
      setBusy("");
      setError(response.message);
      return;
    }
    await load(platformId, sceneId);
    finish("提示词已保存，后续真实模型生成请求将使用新配置。");
    window.dispatchEvent(new Event("workbench:status-changed"));
  }

  async function aiDraft(mode: "current" | "new-platform" | "new-scene") {
    if (demoMode || !modelReady) {
      setError("AI 生成提示词需要可用的真实 LLM。请先保存模型设置并配置 LLM_API_KEY。");
      return;
    }
    if (!requirements.trim()) {
      setError("请先填写需求约束。");
      return;
    }
    begin("ai");
    const payload: any = { requirements };
    if (mode === "new-platform") {
      Object.assign(payload, {
        target_type: "platform", platform_name: newPlatform.name,
        platform_description: newPlatform.description, rule_profile: newPlatform.rule_profile,
        current_prompt: newPlatform.prompt_text,
      });
    } else if (mode === "new-scene") {
      Object.assign(payload, {
        target_type: "scene", platform_id: platformId, scene_name: newScene.name,
        scene_description: newScene.description, rule_content_type: newScene.rule_content_type,
        current_prompt: newScene.prompt_text,
      });
    } else {
      Object.assign(payload, {
        target_type: target,
        platform_id: target === "base" ? undefined : platformId,
        scene_id: target === "scene" ? sceneId : undefined,
        current_prompt: target === "base"
          ? basePrompt
          : target === "platform" ? platformDraft.prompt_text : sceneDraft.prompt_text,
      });
    }
    const response = await api.promptAiDraft(payload);
    if (!response.success) {
      setBusy("");
      setError(response.message);
      return;
    }
    if (mode === "new-platform") setNewPlatform((value) => ({ ...value, prompt_text: response.data.draft }));
    else if (mode === "new-scene") setNewScene((value) => ({ ...value, prompt_text: response.data.draft }));
    else if (target === "base") setBasePrompt(response.data.draft);
    else if (target === "platform") setPlatformDraft((value) => ({ ...value, prompt_text: response.data.draft }));
    else setSceneDraft((value) => ({ ...value, prompt_text: response.data.draft }));
    finish(`AI 草稿已放入编辑器（${response.data.model}），尚未保存。`);
  }

  async function createPlatform() {
    begin("create-platform");
    const response = await api.createPromptPlatform(newPlatform);
    if (!response.success) {
      setBusy("");
      setError(response.message);
      return;
    }
    setNewPlatform({ ...EMPTY_PLATFORM });
    await load(response.data.id, "");
    finish("自定义平台已创建。");
  }

  async function createScene() {
    if (!platform) return;
    begin("create-scene");
    const response = await api.createPromptScene(platform.id, newScene);
    if (!response.success) {
      setBusy("");
      setError(response.message);
      return;
    }
    setNewScene({ ...EMPTY_SCENE });
    await load(platform.id, response.data.id);
    finish("自定义场景已创建。");
  }

  async function togglePlatform() {
    if (!platform || platform.is_builtin) return;
    begin("toggle-platform");
    const response = platform.active
      ? await api.deactivatePromptPlatform(platform.id)
      : await api.activatePromptPlatform(platform.id);
    if (!response.success) setError(response.message);
    await load(platform.id, sceneId);
    finish(response.success ? `平台已${platform.active ? "停用" : "启用"}。` : "");
  }

  async function toggleScene() {
    if (!scene || scene.is_builtin) return;
    begin("toggle-scene");
    const response = scene.active
      ? await api.deactivatePromptScene(scene.id)
      : await api.activatePromptScene(scene.id);
    if (!response.success) setError(response.message);
    await load(platformId, scene.id);
    finish(response.success ? `场景已${scene.active ? "停用" : "启用"}。` : "");
  }

  async function resetCurrent() {
    if (!confirm("确定恢复这一层的系统默认提示词？")) return;
    begin("reset");
    const response = target === "base"
      ? await api.resetBasePrompt()
      : target === "platform" && platform
        ? await api.resetPlatformPrompt(platform.id)
        : target === "scene" && scene
          ? await api.resetScenePrompt(scene.id)
          : null;
    if (!response || !response.success) {
      setBusy("");
      setError(response && !response.success ? response.message : "当前项目没有系统默认提示词。");
      return;
    }
    await load(platformId, sceneId);
    finish("已恢复系统默认提示词。");
  }

  async function resetAllBuiltins() {
    if (!confirm("确定恢复公共层以及全部内置平台、场景的系统默认提示词？自定义平台和场景不会受影响。")) return;
    begin("reset-all");
    const response = await api.resetBuiltinPrompts();
    if (!response.success) {
      setBusy("");
      setError(response.message);
      return;
    }
    await load(platformId, sceneId);
    finish("全部内置提示词已恢复默认。");
  }

  if (!catalog) return <div className="card">正在加载提示词目录……</div>;
  const currentPrompt = target === "base"
    ? basePrompt
    : target === "platform" ? String(platformDraft.prompt_text || "") : String(sceneDraft.prompt_text || "");
  const setCurrentPrompt = (value: string) => {
    if (target === "base") setBasePrompt(value);
    else if (target === "platform") setPlatformDraft((item) => ({ ...item, prompt_text: value }));
    else setSceneDraft((item) => ({ ...item, prompt_text: value }));
  };
  const canReset = target === "base"
    || (target === "platform" && !!platform?.is_builtin)
    || (target === "scene" && !!scene?.is_builtin);

  return <div className="card" style={{ marginTop: 16 }}>
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 12 }}>
      <div><b>生成提示词与场景目录</b><div style={{ fontSize: 12, color: "#6b7280", marginTop: 3 }}>模板 {catalog.version} · {catalog.platforms.length} 个平台 · {catalog.platforms.reduce((sum, item) => sum + item.scenes.length, 0)} 个场景</div></div>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn" onClick={resetAllBuiltins} disabled={!!busy}>恢复全部内置默认</button>
        <button className="btn" onClick={() => load()} disabled={!!busy}><RefreshCw size={15} />刷新</button>
      </div>
    </div>
    {error && <Notice color="#b91c1c" background="#fef2f2">{error}</Notice>}
    {message && <Notice color="#166534" background="#f0fdf4">{message}</Notice>}

    <div className="prompt-manager-grid">
      <div style={{ display: "grid", gap: 10, alignContent: "start" }}>
        <Field label="平台">
          <select className="select" value={platformId} onChange={(event) => setPlatformId(event.target.value)}>
            {catalog.platforms.map((item) => <option key={item.id} value={item.id}>{item.name}{item.active ? "" : "（已停用）"}{item.is_builtin ? " · 内置" : ""}</option>)}
          </select>
        </Field>
        {platform && <>
          <Field label="平台名称"><input className="input" disabled={platform.is_builtin} value={String(platformDraft.name || "")} onChange={(event) => setPlatformDraft((item) => ({ ...item, name: event.target.value }))} /></Field>
          <Field label="平台用途"><input className="input" value={String(platformDraft.description || "")} onChange={(event) => setPlatformDraft((item) => ({ ...item, description: event.target.value }))} /></Field>
          <Field label="合规规则画像"><select className="select" disabled={platform.is_builtin} value={String(platformDraft.rule_profile || "通用")} onChange={(event) => setPlatformDraft((item) => ({ ...item, rule_profile: event.target.value }))}>{catalog.rule_profiles.map((item) => <option key={item}>{item}</option>)}</select></Field>
          {!platform.is_builtin && <button className="btn" onClick={togglePlatform} disabled={!!busy}>{platform.active ? "停用平台" : "重新启用平台"}</button>}
        </>}
        <Field label="场景">
          <select className="select" value={sceneId} onChange={(event) => setSceneId(event.target.value)}>
            {platform?.scenes.map((item) => <option key={item.id} value={item.id}>{item.name}{item.active ? "" : "（已停用）"}{item.is_builtin ? " · 内置" : ""}</option>)}
          </select>
        </Field>
        {scene && <>
          <Field label="场景名称"><input className="input" disabled={scene.is_builtin} value={String(sceneDraft.name || "")} onChange={(event) => setSceneDraft((item) => ({ ...item, name: event.target.value }))} /></Field>
          <Field label="场景用途"><input className="input" value={String(sceneDraft.description || "")} onChange={(event) => setSceneDraft((item) => ({ ...item, description: event.target.value }))} /></Field>
          <Field label="合规内容类型"><select className="select" disabled={scene.is_builtin} value={String(sceneDraft.rule_content_type || "通用")} onChange={(event) => setSceneDraft((item) => ({ ...item, rule_content_type: event.target.value }))}>{catalog.content_rule_profiles.map((item) => <option key={item}>{item}</option>)}</select></Field>
          {!scene.is_builtin && <button className="btn" onClick={toggleScene} disabled={!!busy}>{scene.active ? "停用场景" : "重新启用场景"}</button>}
        </>}
      </div>

      <div style={{ display: "grid", gap: 10, alignContent: "start" }}>
        <Field label="编辑层级">
          <select className="select" value={target} onChange={(event) => setTarget(event.target.value as EditorTarget)}>
            <option value="base">公共基础提示词</option>
            <option value="platform">当前平台提示词</option>
            <option value="scene">当前场景提示词</option>
          </select>
        </Field>
        <textarea className="textarea" maxLength={30000} style={{ minHeight: 320 }} value={currentPrompt} onChange={(event) => setCurrentPrompt(event.target.value)} />
        <div style={{ fontSize: 12, color: "#6b7280" }}>{currentPrompt.length}/30000；结构化生成参数会由系统单独传递。合规约束和统一自检层不可编辑。</div>
        <Field label="交给 AI 的需求约束">
          <textarea className="textarea" maxLength={5000} value={requirements} onChange={(event) => setRequirements(event.target.value)} placeholder="例如：面向首次接触医美的用户，语气克制，突出流程和注意事项，避免强推销。" />
        </Field>
        {(demoMode || !modelReady) && <Notice color="#92400e" background="#fffbeb">当前未启用可用的真实 LLM，AI 生成提示词暂不可用。</Notice>}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <button className="btn btn-primary" onClick={saveCurrent} disabled={!!busy || !currentPrompt.trim()}><Save size={15} />保存当前层</button>
          <button className="btn" onClick={() => aiDraft("current")} disabled={!!busy || demoMode || !modelReady}><Bot size={15} />AI 生成/优化</button>
          {canReset && <button className="btn" onClick={resetCurrent} disabled={!!busy}>恢复默认</button>}
        </div>
        <details><summary style={{ cursor: "pointer", fontSize: 13 }}>查看系统锁定的统一自检提示词</summary><pre className="prompt-preview">{catalog.self_check_prompt}</pre></details>
      </div>
    </div>

    <div className="prompt-manager-grid" style={{ borderTop: "1px solid #e5e7eb", paddingTop: 16, marginTop: 16 }}>
      <CreateBox title="新增自定义平台">
        <Field label="名称"><input className="input" value={newPlatform.name} onChange={(event) => setNewPlatform((item) => ({ ...item, name: event.target.value }))} /></Field>
        <Field label="用途说明"><input className="input" value={newPlatform.description} onChange={(event) => setNewPlatform((item) => ({ ...item, description: event.target.value }))} /></Field>
        <Field label="合规画像"><select className="select" value={newPlatform.rule_profile} onChange={(event) => setNewPlatform((item) => ({ ...item, rule_profile: event.target.value }))}>{catalog.rule_profiles.map((item) => <option key={item}>{item}</option>)}</select></Field>
        <Field label="平台提示词"><textarea className="textarea" maxLength={30000} value={newPlatform.prompt_text} onChange={(event) => setNewPlatform((item) => ({ ...item, prompt_text: event.target.value }))} /></Field>
        <div style={{ display: "flex", gap: 8 }}><button className="btn" onClick={() => aiDraft("new-platform")} disabled={!!busy || demoMode || !modelReady}><Bot size={15} />AI 起草</button><button className="btn btn-primary" onClick={createPlatform} disabled={!!busy || !newPlatform.name.trim() || !newPlatform.prompt_text.trim()}><Plus size={15} />创建平台</button></div>
      </CreateBox>
      <CreateBox title={`为“${platform?.name || "当前平台"}”新增场景`}>
        <Field label="名称"><input className="input" value={newScene.name} onChange={(event) => setNewScene((item) => ({ ...item, name: event.target.value }))} /></Field>
        <Field label="用途说明"><input className="input" value={newScene.description} onChange={(event) => setNewScene((item) => ({ ...item, description: event.target.value }))} /></Field>
        <Field label="合规内容类型"><select className="select" value={newScene.rule_content_type} onChange={(event) => setNewScene((item) => ({ ...item, rule_content_type: event.target.value }))}>{catalog.content_rule_profiles.map((item) => <option key={item}>{item}</option>)}</select></Field>
        <Field label="场景提示词"><textarea className="textarea" maxLength={30000} value={newScene.prompt_text} onChange={(event) => setNewScene((item) => ({ ...item, prompt_text: event.target.value }))} /></Field>
        <div style={{ display: "flex", gap: 8 }}><button className="btn" onClick={() => aiDraft("new-scene")} disabled={!!busy || demoMode || !modelReady || !platform}><Bot size={15} />AI 起草</button><button className="btn btn-primary" onClick={createScene} disabled={!!busy || !platform || !newScene.name.trim() || !newScene.prompt_text.trim()}><Plus size={15} />创建场景</button></div>
      </CreateBox>
    </div>
  </div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label><div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{label}</div>{children}</label>;
}
function Notice({ color, background, children }: { color: string; background: string; children: React.ReactNode }) {
  return <div style={{ color, background, borderRadius: 8, padding: 9, fontSize: 13, marginBottom: 8 }}>{children}</div>;
}
function CreateBox({ title, children }: { title: string; children: React.ReactNode }) {
  return <div style={{ display: "grid", gap: 9, alignContent: "start" }}><b style={{ fontSize: 14 }}>{title}</b>{children}</div>;
}
