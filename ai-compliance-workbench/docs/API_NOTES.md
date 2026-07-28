# API notes

核心接口：

- `POST /api/generation/generate`：生成并检测；开启历史记录后自动保存并返回 `history_saved`、`history_record_id`；
- `POST /api/generation/rewrite`：显式改写，并返回改写前后检测；
- `POST /api/generation/adjust`：仅调整请求中的当前文案，不重新套用生成模板；返回 `text`、`original_text`、`adjust_type` 和调整后检测结果；
- `POST /api/compliance/check`：检测文本；
- `GET /api/compliance/rules`：分页查询规则；
- `GET /api/compliance/rules/{rule_id}`：规则、变体、平台、示例及来源；
- `POST /api/compliance/validate`：校验规则结构与引用；
- `POST /api/compliance/test-suite`：执行规则回归测试。
- `GET /api/status`：返回规则版本、数量、待人工复核数量和运行模式。

所有业务响应均使用：

```json
{
  "success": true,
  "data": {},
  "message": null,
  "request_id": ""
}
```

`/api/status`、`/api/compliance/validate` 和 `/api/compliance/reload` 均包含 `pending_review_count`。v1.2 当前值为 56。`/api/status` 还返回 `configured_provider`、`active_provider`、`provider_ready`、`api_key_configured` 和实际 `model_name`。

语义检测失败时不返回“通过”，而是：

```json
{
  "semantic_analysis_failed": true,
  "manual_review_required": true,
  "publish_recommendation": "manual_review"
}
```
