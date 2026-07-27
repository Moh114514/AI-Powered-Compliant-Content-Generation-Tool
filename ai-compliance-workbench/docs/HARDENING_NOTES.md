# Web Workbench hardening notes

本分支集中解决以下问题：

- L1/L4 复核等级聚合方向错误；
- 不同规则命中同一文本区间时被错误去重；
- 语义模型失败后静默返回低风险；
- 语义风险未参与总体风险和发布动作；
- `pending_review` 规则未强制人工复核；
- 生成一次文案可能重复调用改写模型；
- 改写稿未再次执行合规检测；
- 品牌 Prompt 将偏好词误当成禁用词；
- SQLite 默认连接无法安全应对 FastAPI 线程；
- 前端 API 客户端缺少网络错误和超时处理；
- 切换平台后内容类型可能仍保留为无效值；
- 规则查询只读取前 100 条，无法完整生成筛选项；
- 缺少规则库回归测试接口和前端入口；
- CORS 默认配置过宽；
- 缺少启动文档、环境示例和持续集成。

## 新增验收能力

- `POST /api/compliance/test-suite`：执行 `test_cases.json`；
- “工具设置”页面：查看规则数量、警告、测试样本和回归通过率；
- GitHub Actions：运行后端 pytest 与前端 TypeScript/Vite 构建；
- 改写接口返回 `original_compliance` 与 `revised_compliance`；
- 语义检测失败时返回 `semantic_analysis_failed=true` 并强制人工复核。

## 合并前检查

```bash
cd ai-compliance-workbench/backend
python -m pip install -r requirements.txt
python -m pytest -q

cd ../frontend
npm install
npm run build
```

随后在网页“工具设置”中执行数据校验和规则回归测试。
