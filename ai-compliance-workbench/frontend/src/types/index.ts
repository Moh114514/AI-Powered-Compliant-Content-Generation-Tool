// 与后端响应结构对应的类型定义

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string | null;
  request_id: string;
  error_code?: string;
}

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
  loaded_at: string;
  validation_valid: boolean;
  validation_error_count: number;
  demo_mode: boolean;
  platforms: string[];
}

export interface RuleSummary {
  rule_id: string;
  rule_name: string;
  category_code?: string;
  category_name?: string;
  risk_level: string;
  legal_conclusion?: string;
  system_action?: string[];
  effective_status?: string;
  updated_at?: string;
}

export interface RuleDetail {
  rule: Record<string, any>;
  source_ids: string[];
  source_names: string[];
  variants: any[];
  platforms: any[];
}

export interface SourceDetail {
  source_id: string;
  source_name: string;
  source_type?: string;
  issuing_authority?: string;
  [k: string]: any;
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
  spans: HighlightSpan[];
}

export interface HighlightSpan {
  rule_id: string;
  variant_id?: string;
  matched_text: string;
  start_index: number;
  end_index: number;
  matching_method: string;
}

export interface SemanticFinding {
  semantic_rule_id: string;
  semantic_rule_name: string;
  risk_level: string;
  matched_text: string;
  risk_reason?: string;
  manual_review?: boolean;
}

export interface ManualReviewIssue {
  issue_type: string;
  question: string;
  required_evidence: string;
  recommended_contact: string;
}

export interface ComplianceResult {
  input_text: string;
  normalized_text: string;
  platform: string;
  content_type: string;
  overall_risk_level: string;
  review_level: string;
  publish_recommendation: string;
  manual_review_required: boolean;
  matched_rules: MatchedRule[];
  semantic_findings: SemanticFinding[];
  platform_findings: any[];
  manual_review_issues: ManualReviewIssue[];
  suggested_revision: string;
  review_summary: string;
  disclaimer: string;
  highlights: HighlightSpan[];
  platform_rules_incomplete?: boolean;
}

export interface VersionResult {
  version_index: number;
  text: string;
  platform: string;
  content_type: string;
  char_count: number;
  generated_at: string;
  model: string;
  overall_risk_level: string;
  matched_count: number;
  manual_review_required: boolean;
  compliance: ComplianceResult;
}

export interface GenerateResult {
  platform: string;
  content_type: string;
  brand?: string;
  model: string;
  demo_mode: boolean;
  versions: VersionResult[];
  disclaimer: string;
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
