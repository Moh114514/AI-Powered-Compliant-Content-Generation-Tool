// 与后端响应结构对应的类型定义

export type ApiResponse<T> =
  | { success: true; data: T; message: string | null; request_id: string; error_code?: never }
  | { success: false; data: null; message: string; request_id: string; error_code?: string };

export interface Brand {
  brand_id: string;
  brand_name: string;
  short_description?: string;
  tone?: string;
  preferred_terms?: string[];
  prohibited_terms?: string[];
  standard_disclaimer?: string;
  active?: boolean;
  is_demo?: boolean;
}

export interface StatusInfo {
  data_version: string;
  library_name: string;
  rule_count: number;
  variant_count: number;
  source_count: number;
  semantic_count: number;
  test_case_count?: number;
  visual_check_count?: number;
  loaded_at: string;
  validation_valid: boolean;
  validation_error_count: number;
  validation_warning_count?: number;
  pending_review_count?: number;
  demo_mode: boolean;
  configured_provider?: string;
  active_provider?: string;
  provider_ready?: boolean;
  provider_error?: string;
  api_key_configured?: boolean;
  model_name?: string;
  platforms: string[];
  prompt_version?: string;
  prompt_platform_count?: number;
  prompt_scene_count?: number;
  prompt_active_platform_count?: number;
  prompt_active_scene_count?: number;
  prompt_custom_platform_count?: number;
  prompt_custom_scene_count?: number;
  prompt_override_count?: number;
  default_platform_warning?: string;
}

export interface PromptScene {
  id: string;
  platform_id: string;
  name: string;
  description: string;
  prompt_text: string;
  default_prompt: string;
  effective_prompt: string;
  rule_content_type: string;
  sort_order: number;
  is_builtin: boolean;
  active: boolean;
  is_overridden: boolean;
  updated_at?: string;
}

export interface PromptPlatform {
  id: string;
  name: string;
  description: string;
  prompt_text: string;
  default_prompt: string;
  effective_prompt: string;
  rule_profile: string;
  sort_order: number;
  is_builtin: boolean;
  active: boolean;
  is_overridden: boolean;
  scenes: PromptScene[];
  updated_at?: string;
}

export interface PromptCatalog {
  version: string;
  source: string;
  base_prompt: { default: string; effective: string; is_overridden: boolean };
  self_check_prompt: string;
  rule_profiles: string[];
  content_rule_profiles: string[];
  platforms: PromptPlatform[];
}

export interface RuleSummary {
  rule_id: string;
  rule_name: string;
  category_code?: string;
  category_name?: string;
  risk_level: string;
  review_level?: string;
  legal_conclusion?: string;
  system_action?: string[];
  effective_status?: string;
  updated_at?: string;
  variant_count?: number;
  source_count?: number;
}

export interface RuleDetail {
  rule: Record<string, any>;
  source_ids: string[];
  source_names: string[];
  sources?: SourceDetail[];
  variants: any[];
  platforms: any[];
  examples?: any[];
}

export interface SourceDetail {
  source_id: string;
  source_name: string;
  source_type?: string;
  issuing_authority?: string;
  official_url?: string;
  verification_status?: string;
  [key: string]: any;
}

export interface HighlightSpan {
  rule_id: string;
  variant_id?: string;
  matched_text: string;
  start_index: number;
  end_index: number;
  matching_method: string;
}

export interface MatchedRule {
  rule_id: string;
  rule_name: string;
  variant_id?: string;
  matched_text: string;
  start_index: number;
  end_index: number;
  matching_method: string;
  risk_level: string;
  legal_conclusion?: string;
  system_action: string[];
  risk_reason?: string;
  replacement_strategy: string[];
  source_ids: string[];
  source_names: string[];
  category_name?: string;
  prohibited_context?: string;
  allowed_context?: string;
  evidence_requirement?: string;
  qualification_requirement?: string;
  auto_rewrite_allowed?: boolean;
  manual_review_required?: boolean;
  review_level?: string;
  effective_status?: string;
  spans: HighlightSpan[];
}

export interface SemanticFinding {
  semantic_rule_id: string;
  semantic_rule_name: string;
  risk_level: string;
  matched_text: string;
  risk_reason?: string;
  manual_review?: boolean;
  system_action?: string[];
}

export interface ManualReviewIssue {
  issue_type: string;
  rule_id?: string;
  semantic_rule_id?: string;
  question: string;
  required_evidence: string;
  recommended_contact: string;
}

export interface ComplianceStats {
  applicable_rule_count: number;
  matched_rule_count: number;
  matched_span_count: number;
  semantic_finding_count: number;
}

export interface ComplianceResult {
  input_text: string;
  normalized_text: string;
  platform: string;
  content_type: string;
  platform_id?: string;
  scene_id?: string;
  overall_risk_level: string;
  review_level: string;
  publish_recommendation: string;
  manual_review_required: boolean;
  matched_rules: MatchedRule[];
  semantic_findings: SemanticFinding[];
  semantic_analysis_failed?: boolean;
  platform_findings: Array<{ type?: string; risk_level?: string; message?: string; [key: string]: any }>;
  manual_review_issues: ManualReviewIssue[];
  suggested_revision: string;
  review_summary: string;
  disclaimer: string;
  highlights: HighlightSpan[];
  platform_rules_incomplete?: boolean;
  stats?: ComplianceStats;
  timings_ms?: { deterministic: number; semantic: number; rewrite: number; total: number };
  history_saved?: boolean;
  history_record_id?: string;
  history_error?: string;
}

export interface VersionResult {
  version_index: number;
  text: string;
  platform: string;
  content_type: string;
  platform_id?: string;
  scene_id?: string;
  char_count: number;
  generated_at: string;
  model: string;
  provider?: string;
  overall_risk_level: string;
  matched_count: number;
  manual_review_required: boolean;
  compliance: ComplianceResult;
}

export interface GenerateResult {
  platform: string;
  content_type: string;
  platform_id?: string;
  scene_id?: string;
  brand?: string;
  model: string;
  provider?: string;
  demo_mode: boolean;
  requested_versions?: number;
  returned_versions?: number;
  versions: VersionResult[];
  timings_ms?: { prompt_assembly: number; model_generation: number; compliance_all_versions: number; total: number };
  disclaimer: string;
  history_saved?: boolean;
  history_record_id?: string;
  history_error?: string;
}

export interface HistoryRecord {
  id: string;
  operation_type: string;
  brand?: string;
  platform?: string;
  input: any;
  generated?: GenerateResult | null;
  detection?: ComplianceResult | null;
  risk_level?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Settings {
  model_provider?: string;
  model_name?: string;
  api_base?: string;
  temperature?: number;
  max_tokens?: number;
  default_brand?: string;
  default_platform?: string;
  default_versions?: number;
  default_tone?: string;
  default_length?: string;
  auto_semantic_check?: boolean;
  enable_keyword_detection?: boolean;
  enable_regex_detection?: boolean;
  enable_semantic_detection?: boolean;
  auto_generate_revision?: boolean;
  force_disclaimer?: boolean;
  save_history?: boolean;
  max_history?: number;
  history_retention_days?: number;
}

export interface TestSuiteDetail {
  test_id: string;
  passed: boolean;
  input_text: string;
  platform: string;
  content_type: string;
  expected_rule_ids?: string[];
  actual_rule_ids?: string[];
  missing_rule_ids?: string[];
  expected_risk_level?: string;
  actual_risk_level?: string;
  expected_action?: string;
  actual_action?: string;
  problems: string[];
  error?: string;
}

export interface TestSuiteResult {
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
  failure_type_counts: Record<string, number>;
  category_metrics: Array<{ category: string; total: number; passed: number; pass_rate: number }>;
  details: TestSuiteDetail[];
  details_truncated: boolean;
  engine_mode: string;
  quality_metrics?: {
    risk_detection_recall: number;
    high_risk_false_positive_rate: number;
    expected_rule_id_recall: number;
    risk_level_accuracy: number;
    action_accuracy: number;
    expected_risky_cases: number;
    expected_clean_cases: number;
  };
  note: string;
}
