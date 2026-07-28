# API notes

核心接口：

- `POST /api/generation/generate`：生成并检测；
- `POST /api/generation/rewrite`：显式改写，并返回改写前后检测；
- `POST /api/compliance/check`：检测文本；
- `GET /api/compliance/rules`：分页查询规则；
- `GET /api/compliance/rules/{rule_id}`：规则、变体、平台、示例及来源；
- `POST /api/compliance/validate`：校验规则结构与引用；
- `POST /api/compliance/test-suite`：执行规则回归测试。

所有业务响应均使用：

```json
{
  "success": true,
  "data": {},
  "message": null,
  "request_id": ""
}
```

语义检测失败时不返回“通过”，而是：

```json
{
  "semantic_analysis_failed": true,
  "manual_review_required": true,
  "publish_recommendation": "manual_review"
}
```
