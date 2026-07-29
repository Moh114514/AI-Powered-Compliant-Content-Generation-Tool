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

`/api/status`、`/api/compliance/validate` 和 `/api/compliance/reload` 均包含 `pending_review_count`。v1.2 当前值为 56。`/api/status` 还返回模型状态，以及小红书专项词库的版本、条目数、变体数、唯一词数、SHA-256 和加载警告。

小红书或映射到小红书规则画像的平台执行检测时，结果包含 `banned_word_hits`。结果按标准词聚合，每项提供 `hit_id`、首次命中区间、标准词、领域、风险等级、原因、替换建议、来源、语境分类、人工复核标记，以及 `occurrence_count` 和全部 `spans`。旧调用方仍可读取原有的 `start`、`end`、`matched_text` 字段。

`stats.banned_word_unique_count` 表示不同风险词数量，`stats.banned_word_occurrence_count` 表示正文中的实际出现次数。

语义检测失败时不返回“通过”，而是：

```json
{
  "semantic_analysis_failed": true,
  "semantic_failure_reason": "模型服务资源不足，请稍后重试。",
  "manual_review_required": true,
  "publish_recommendation": "manual_review"
}
```

真实模型的语义检测使用 4096 Token、非思考模式和 JSON Output。空内容或非法 JSON 最多重试一次；最终失败原因会区分 Token 截断、内容过滤、资源不足、响应缺失和格式错误。
