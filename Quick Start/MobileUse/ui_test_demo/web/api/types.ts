export type SetupStatus = {
  initialized: boolean;
};

export type User = {
  id: number;
  username: string;
  display_name: string | null;
  email: string | null;
  role: "admin" | "member";
  status: "active" | "disabled";
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
};

export type UserListResponse = {
  items: User[];
};

export type BusinessSpace = {
  id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  task_concurrency_limit: number;
  archived_at: string | null;
  created_by: string;
};

export type BusinessSpaceListResponse = {
  items: BusinessSpace[];
};

export type UserCreate = {
  username: string;
  password: string;
  display_name?: string | null;
  email?: string | null;
  role: "admin" | "member";
};

export type UserBatchCreate = {
  users: UserCreate[];
};

export type UserUpdate = {
  display_name?: string | null;
  email?: string | null;
  role?: "admin" | "member";
};

export type UserPasswordReset = {
  new_password: string;
  confirm_password: string;
};

export type Credentials = {
  username: string;
  password: string;
};

export type RunnerMode = "mock" | "mobile_use";
export type DevicePrepareAction = "none" | "reset" | "reboot";

export type SecretState = {
  configured: boolean;
};

export type AccessKeyState = SecretState & {
  hint: string | null;
};

export type MobileUseSettings = {
  access_key_id: AccessKeyState;
  secret_access_key: SecretState;
  product_id: string | null;
  account_id: string | null;
  sts_role_trn: string | null;
  stream_token_ttl_seconds: number;
  pod_id: string | null;
  ark_api_key: SecretState;
  tos_bucket: string | null;
  tos_endpoint: string | null;
  tos_region: string | null;
  use_base64_screenshot: boolean;
  max_step: number;
  timeout_seconds: number;
  callback_info: Record<string, unknown> | null;
  output_schema: string | null;
  retry_limit: number;
  system_prompt: string | null;
  screen_record: boolean;
  mcp_json: string | null;
  max_output_tokens: number | null;
  gps_info: string | null;
  device_prepare_action: DevicePrepareAction;
  request_headers: {
    configured: boolean;
    names: string[];
    items?: Array<{ name: string; value: string }>;
  };
};

export type AgentRuntimeOptions = {
  thread_id?: string | null;
  use_base64_screenshot?: boolean | null;
  max_step?: number | null;
  timeout_seconds?: number | null;
  callback_info?: Record<string, unknown> | null;
  output_schema?: string | null;
  retry_limit?: number | null;
  system_prompt?: string | null;
  tos_bucket?: string | null;
  tos_endpoint?: string | null;
  tos_region?: string | null;
  screen_record?: boolean | null;
  mcp_json?: string | null;
  max_output_tokens?: number | null;
  gps_info?: string | null;
  device_prepare_action?: DevicePrepareAction | null;
  request_headers?: Record<string, string> | null;
};

export type SettingsResponse = {
  mode: RunnerMode;
  mobile_use: MobileUseSettings;
};

export type RunnerSettingsUpdate = {
  mode: RunnerMode;
  mobile_use?: Partial<
    Record<
      | "access_key_id"
      | "secret_access_key"
      | "product_id"
      | "account_id"
      | "sts_role_trn"
      | "stream_token_ttl_seconds"
      | "pod_id"
      | "ark_api_key"
      | "tos_bucket"
      | "tos_endpoint"
      | "tos_region"
      | "use_base64_screenshot"
      | "max_step"
      | "timeout_seconds"
      | "callback_info"
      | "output_schema"
      | "retry_limit"
      | "system_prompt"
      | "screen_record"
      | "mcp_json"
      | "max_output_tokens"
      | "gps_info"
      | "device_prepare_action"
      | "request_headers",
      string | number | boolean | Record<string, unknown> | null
    >
  >;
};

export type PasswordUpdate = {
  current_password: string;
  new_password: string;
};

export type RunnerCheckName = "credentials" | "runner_api" | "pod";
export type DiagnosticStatus = "passed" | "failed";
export type PodStatus = "available" | "busy" | "offline" | "unknown";
export type PodDiagnosticCode =
  | "pod_available"
  | "pod_not_found"
  | "pod_unavailable"
  | "credentials_invalid"
  | "permission_denied"
  | "runner_api_unreachable"
  | "runner_api_unavailable"
  | "request_rejected"
  | "diagnostic_timeout"
  | "diagnostic_internal_error";

export type RunnerDiagnosticCheck = {
  name: RunnerCheckName;
  status: DiagnosticStatus;
  code: string;
  message: string;
  request_id: string | null;
};

export type RunnerDiagnosticResult = {
  runner_mode: RunnerMode;
  status: DiagnosticStatus;
  checked_at: string;
  checks: RunnerDiagnosticCheck[];
};

export type PodDiagnostic = {
  pod_id: string;
  status: PodStatus;
  product_id: string;
  code: PodDiagnosticCode;
  message: string;
  request_id: string | null;
};

export type PodDiagnosticsResponse = {
  items: PodDiagnostic[];
  checked_at: string;
};

export type PodLocalState =
  | "available"
  | "leased"
  | "cooldown"
  | "stale"
  | "unavailable";

export type PodHostAction = {
  action: "reset" | "reboot" | "power_on" | "power_off";
  request_id: string | null;
  remote_task_id: string;
  status: "running" | "succeeded" | "failed";
  task_result: number | null;
  task_message: string | null;
};

export type PodPoolItem = {
  product_id: string;
  pod_id: string;
  pod_name: string;
  pod_status_code: number;
  stream_status: number | null;
  discovery_state: "active" | "stale";
  local_state: PodLocalState;
  image_id: string | null;
  image_name: string | null;
  aosp_version: string | null;
  display_layout_id: string | null;
  dc_id: string | null;
  dc_name: string | null;
  isp_code: number | null;
  region: string | null;
  zone_id: string | null;
  config_code: string | null;
  config_name: string | null;
  config_type: number | null;
  server_type_code: string | null;
  intranet_ip: string | null;
  adb_address: string | null;
  adb_status: number | null;
  data_size: string | null;
  data_size_used: string | null;
  pod_created_at: string | null;
  last_seen_at: string;
  last_checked_at: string | null;
  request_id: string | null;
  task_id: string | null;
  task_status: ExecutionStatus | null;
  task_scenario: string | null;
  active_host_action?: PodHostAction | null;
  eip_address: string | null;
};

export type PodDetail = {
  product_id: string;
  pod_id: string;
  pod_name: string;
  pod_status_code: number;
  stream_status: number | null;
  image_id: string | null;
  image_name: string | null;
  aosp_version: string | null;
  display_layout_id: string | null;
  dc_id: string | null;
  dc_name: string | null;
  isp_code: number | null;
  region: string | null;
  zone_id: string | null;
  config_code: string | null;
  config_name: string | null;
  config_type: number | null;
  server_type_code: string | null;
  intranet_ip: string | null;
  adb_address: string | null;
  adb_status: number | null;
  data_size: string | null;
  data_size_used: string | null;
  pod_created_at: string | null;
  request_id: string | null;
  eip_address: string | null;
};

export type PodPoolResponse = {
  items: PodPoolItem[];
  refreshed_at: string | null;
};

export type PodStreamToken = {
  AccessKeyID: string;
  SecretAccessKey: string;
  SessionToken: string;
  CurrentTime: string;
  ExpiredTime: string;
};

export type PodStreamSession = {
  account_id: string;
  product_id: string;
  pod_id: string;
  user_id: string;
  token: PodStreamToken;
};

export type AutomationLevel = "auto" | "assisted" | "manual_confirm";

export type TestCaseCreate = {
  title: string;
  module?: string | null;
  content_markdown: string;
  tags?: string[];
  automation_level?: AutomationLevel;
  default_agent_options?: AgentRuntimeOptions | null;
};

export type TestCaseUpdate = Partial<TestCaseCreate>;

export type TestCase = {
  id: string;
  title: string;
  module: string | null;
  content_markdown: string;
  tags: string[];
  automation_level: AutomationLevel;
  default_agent_options?: AgentRuntimeOptions | null;
  execution_count: number;
  pass_count: number;
  fail_count: number;
  last_executed_at: string | null;
  bound_plan_count?: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type TestCaseListResponse = {
  items: TestCase[];
  total: number;
  page: number;
  page_size: number;
};

export type CaseBoundTestPlan = {
  id: string;
  name: string;
  test_type: TestType;
  case_count: number;
  has_active_execution: boolean;
  created_by: string;
  updated_at: string;
};

export type CaseBoundTestPlanListResponse = {
  items: CaseBoundTestPlan[];
  total: number;
  page: number;
  page_size: number;
};

export type CaseImportFormat = "csv" | "markdown" | "excel";

export type CaseImportPreviewItem = {
  row: number;
  status: "valid" | "warning" | "error";
  messages: string[];
  draft: TestCaseCreate;
};

export type CaseImportPreviewResponse = {
  items: CaseImportPreviewItem[];
  summary: {
    total: number;
    valid: number;
    warning: number;
    error: number;
  };
};

export type CaseImportConfirmResponse = {
  created_count: number;
  items: TestCase[];
};

export type CaseStats = {
  total: number;
  auto_count: number;
  today_executions: number;
  total_executions: number;
  pass_rate: number;
};

export type TagListResponse = {
  items: string[];
};

export type CreatorListResponse = {
  items: string[];
};

export type ModuleListResponse = {
  items: string[];
};

export type CaseExecuteRequest = {
  idempotency_key?: string;
  pod_id?: string | null;
  timeout_seconds?: number | null;
  agent_config_mode?: "global" | "custom" | "case_default";
  agent_options?: AgentRuntimeOptions | null;
};

export type CaseBatchDeleteItem = {
  case_id: string;
  status: "deleted" | "failed";
  code: string | null;
  message: string | null;
};

export type CaseBatchDeleteResponse = {
  deleted_count: number;
  failed_count: number;
  items: CaseBatchDeleteItem[];
};

export type ExecutionStatus =
  | "queued"
  | "running"
  | "result_ready"
  | "cancelled";

export type Verdict = "pass" | "fail";

export type TaskStats = {
  total: number;
  running: number;
  queued: number;
  pass_rate: number;
  manual_review_fail_count?: number;
  manual_review_total?: number;
  manual_review_fail_rate?: number;
};

export type TaskOperatorListResponse = {
  items: string[];
};

export type TaskExecutionConfig = {
  source: "global" | "custom" | "case_default" | "legacy";
  product_id: string | null;
  pod_id: string | null;
  device_strategy?: "automatic" | "specified" | string | null;
  pod_ids?: string[] | null;
  tos_bucket: string | null;
  tos_endpoint: string | null;
  tos_region: string | null;
  timeout_seconds: number | null;
  device_wait_timeout_seconds: number | null;
  use_base64_screenshot: boolean | null;
  max_step: number | null;
  callback_info: Record<string, unknown> | null;
  output_schema: string | null;
  retry_limit: number | null;
  system_prompt: string | null;
  screen_record: boolean | null;
  mcp_json: string | null;
  max_output_tokens: number | null;
  gps_info: string | null;
  device_prepare_action: DevicePrepareAction;
  request_headers: {
    configured: boolean;
    names: string[];
    items?: Array<{ name: string; value: string }>;
  };
};

export type Task = {
  id: string;
  case_id: string;
  batch_id?: string | null;
  batch_position?: number | null;
  display_task_id?: string;
  source_type?: "single_case" | "multi_cases";
  queue_reason?: string | null;
  script_version_id: string | null;
  prompt_snapshot: string | null;
  result_summary: string | null;
  result_evidence: string[];
  remote_thread_id?: string | null;
  remote_status_code?: number | null;
  remote_step_id?: string | null;
  recording_url?: string | null;
  result_assets?: RuntimeAssets;
  runner_type: string;
  scenario: string;
  created_by: string;
  execution_status: ExecutionStatus;
  verdict: Verdict | null;
  review_result?: Verdict | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  failure_type: string | null;
  version: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type TaskList = {
  items: Task[];
};

export type TaskListPage = {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
};

export type TaskBatchCreateRequest = {
  name: string;
  test_type: "new_feature" | "regression";
  selection_mode: "multi_cases" | "tags" | "test_plan";
  case_ids: string[];
  selection_snapshot: Record<string, unknown>;
  device_strategy: "automatic" | "specified";
  pod_ids: string[];
  concurrency: number;
  device_wait_timeout_seconds?: number | null;
  timeout_seconds?: number | null;
  agent_config_mode: "global" | "custom" | "case_default";
  agent_options?: AgentRuntimeOptions | null;
  idempotency_key: string;
};

export type TaskBatch = {
  id: string;
  name: string;
  test_type: "new_feature" | "regression";
  selection_mode: "multi_cases" | "tags" | "test_plan";
  selection_snapshot: Record<string, unknown>;
  device_strategy: "automatic" | "specified";
  pod_ids: string[];
  concurrency: number;
  device_wait_timeout_seconds: number;
  execution_status: ExecutionStatus;
  verdict: Verdict | null;
  created_by: string;
  unavailable_since: string | null;
  cancel_requested_at: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  tasks: Task[];
};

export type TaskEvent = {
  sequence: number;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type TaskEventList = {
  items: TaskEvent[];
};

export type TraceAttribute = string | number | boolean | null;

export type TaskTraceSpan = {
  id: string;
  parent_span_id: string | null;
  sequence: number;
  kind: string;
  name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  request_id: string | null;
  step_index: number | null;
  error_code: string | null;
  attributes: Record<string, TraceAttribute>;
  children?: TaskTraceSpan[];
};

export type TaskTrace = {
  task_id: string;
  source: "spans" | "events";
  view: "tree" | "flat";
  execution_status: ExecutionStatus;
  verdict: Verdict | null;
  failure_type: string | null;
  spans: TaskTraceSpan[];
};

export type TaskReport = {
  task_id: string;
  title: string;
  case_id: string;
  execution_status: ExecutionStatus;
  verdict: Verdict | null;
  failure_type: string | null;
  summary: string | null;
  evidence: string[];
  recording_url?: string | null;
  assets?: RuntimeAssets;
};

export type RuntimeAssets = {
  content?: string;
  struct_output?: Record<string, unknown>;
  screenshots?: Record<string, RuntimeScreenshot>;
  usage?: {
    in_tokens?: number | string;
    out_tokens?: number | string;
  };
  files?: string[];
  duration_ms?: number;
  duration_fmt?: string;
  avg_step_duration_sec?: number;
};

export type RuntimeScreenshot = {
  id?: string;
  screenshot?: string;
  original_screenshot?: string;
  original_dimensions?: number[];
  screenshot_dimensions?: number[];
};

export type RuntimeToolCallResult = {
  Action?: string;
  Param?: Record<string, unknown>;
  StepResult?: Record<string, unknown>;
  Timestamp?: string;
};

export type RuntimeCurrentStep = {
  run_id: string | null;
  thread_id: string | null;
  status: number | null;
  step_id: string | null;
  results: RuntimeToolCallResult[];
  error?: string | null;
};

export type RuntimeThreadTask = {
  run_id: string | null;
  thread_id: string | null;
  run_name: string | null;
  status: number | null;
  pod_id: string | null;
  product_id: string | null;
  created_at: string | null;
  started_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
  trace_id: string | null;
  artifact_count: Record<string, number> | null;
};

export type RuntimeThreadGroup = {
  thread_id: string | null;
  tasks: RuntimeThreadTask[];
  task_next_token: string | null;
};

export type RuntimeThreadStep = {
  run_id: string | null;
  thread_id: string | null;
  status: number | null;
  step_id: string | null;
  results: RuntimeToolCallResult[];
};

export type RuntimeCurrentPhase = {
  type: "device_prepare";
  status: "running";
  action: "reset" | "reboot";
  product_id: string | null;
  pod_id: string | null;
};

export type TaskRuntimeResponse = {
  task: Task;
  execution_config: TaskExecutionConfig;
  current_phase: RuntimeCurrentPhase | null;
  current_step: RuntimeCurrentStep | null;
  thread_groups: RuntimeThreadGroup[];
  thread_steps: RuntimeThreadStep[];
  result: {
    summary: string | null;
    evidence: string[];
    recording_url: string | null;
    assets: RuntimeAssets;
  };
  errors: Record<string, string>;
};

export type TagOption = {
  name: string;
  foreground_color: string;
  background_color: string;
  case_count: number | null;
};

export type TagOptionListResponse = {
  items: TagOption[];
  total: number;
  page: number;
  page_size: number;
};

export type ReportStatus =
  | "queued"
  | "running"
  | "success"
  | "failure"
  | "exception"
  | "cancelled";

export type TestType = "new_feature" | "regression";

export type LatestPlanExecution = {
  execution_id: string;
  task_batch_id: string;
  report_status: ReportStatus;
  pass_rate: number;
  created_at: string;
};

export type ScheduleSummary = {
  enabled: boolean;
  cron_expr: string;
  next_run_at: string | null;
  last_run_at: string | null;
};

export type TestPlan = {
  id: string;
  name: string;
  description: string | null;
  test_type: TestType;
  tags: TagOption[];
  case_ids: string[];
  case_count: number;
  execution_count: number;
  latest_execution: LatestPlanExecution | null;
  schedule?: ScheduleSummary | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type TestPlanResponse = TestPlan;

export type TestPlanWrite = {
  name: string;
  description?: string | null;
  test_type: TestType;
  tags?: string[];
  case_ids: string[];
};

export type TestPlanListResponse = {
  items: TestPlan[];
  total: number;
  page: number;
  page_size: number;
};

export type TestPlanStats = {
  active_plan_count: number;
  distinct_case_count: number;
  execution_count: number;
  latest_completed_pass_rate: number;
};

export type TestPlanStatsResponse = TestPlanStats;

export type TestPlanCaseListResponse = {
  items: TestCase[];
  total: number;
  page: number;
  page_size: number;
};

export type PlanExecutionCreate = {
  test_type: TestType;
  device_strategy: "automatic" | "specified";
  pod_ids: string[];
  concurrency: number;
  device_wait_timeout_seconds?: number | null;
  timeout_seconds?: number | null;
  agent_config_mode: "global" | "custom" | "case_default";
  agent_options?: AgentRuntimeOptions | null;
  idempotency_key: string;
};

export type PlanExecution = {
  id: string;
  test_plan_id: string | null;
  task_batch_id: string;
  plan_name_snapshot: string;
  plan_tags_snapshot: string[];
  case_ids_snapshot: string[];
  device_strategy_snapshot: "automatic" | "specified";
  pod_ids_snapshot: string[];
  concurrency_snapshot: number;
  runner_type_snapshot: string;
  config_snapshot: TaskExecutionConfig;
  created_by: string;
  created_at: string;
  batch: TaskBatch;
};

export type PlanExecutionResponse = PlanExecution;

export type PlanReportSummary = {
  execution_id: string;
  task_batch_id: string;
  test_plan_id: string | null;
  plan_name_snapshot: string;
  report_status: ReportStatus;
  pass_rate: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
};

export type PlanReportStats = {
  report_count: number;
  success_count: number;
  failure_count: number;
  average_pass_rate: number;
};

export type PlanReportStatsResponse = PlanReportStats;

export type ReportTaskExecutionStatus =
  | "script_pending"
  | "queued"
  | "running"
  | "result_ready"
  | "cancelled"
  | "unknown";

export type ReportTaskVerdict = Verdict | "unknown";

export type PlanReportTask = {
  task_id: string;
  remote_run_id: string | null;
  case_id: string;
  case_title: string;
  case_deleted: boolean;
  execution_status: ReportTaskExecutionStatus;
  verdict: ReportTaskVerdict | null;
  failure_type: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_steps: number | null;
};

export type PlanReportDetail = PlanReportSummary & {
  plan_tags_snapshot: string[];
  case_ids_snapshot: string[];
  device_strategy_snapshot: "automatic" | "specified";
  pod_ids_snapshot: string[];
  concurrency_snapshot: number;
  runner_type_snapshot: string;
  config_snapshot: TaskExecutionConfig;
  pass_count: number;
  fail_count: number;
  exception_count: number;
  cancelled_count: number;
  queued_count: number;
  running_count: number;
  tasks: PlanReportTask[];
  tasks_total: number;
  page: number;
  page_size: number;
};

export type PlanReportDetailResponse = PlanReportDetail;

export type PlanReportListResponse = {
  items: PlanReportSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type ScheduleEventType = "triggered" | "skipped" | "failed";
export type ScheduleTriggerType = "scheduled" | "manual" | "catchup";

export type ScheduleExecutionConfig = {
  test_type: TestType;
  device_strategy: "automatic" | "specified";
  pod_ids: string[];
  concurrency: number;
  device_wait_timeout_seconds?: number | null;
  timeout_seconds?: number | null;
  agent_config_mode?: "global" | "custom" | "case_default";
  agent_options?: Record<string, unknown> | null;
};

export type TestPlanSchedule = {
  id: string;
  test_plan_id: string;
  cron_expr: string;
  timezone: string;
  enabled: boolean;
  next_run_at: string;
  last_run_at: string | null;
  last_skip_reason: string | null;
  execution_config: ScheduleExecutionConfig;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type TestPlanScheduleCreate = {
  cron_expr: string;
  timezone: string;
  execution_config: ScheduleExecutionConfig;
  enabled?: boolean;
};

export type TestPlanScheduleUpdate = Partial<TestPlanScheduleCreate>;

export type ScheduleEvent = {
  id: string;
  schedule_id: string;
  event_type: ScheduleEventType;
  trigger_type: ScheduleTriggerType;
  scheduled_for: string;
  fired_at: string;
  plan_execution_id: string | null;
  skip_reason: string | null;
  error_message: string | null;
  created_at: string;
};

export type ScheduleEventListResponse = {
  items: ScheduleEvent[];
  total: number;
  page: number;
  page_size: number;
};

export type CronPreviewResponse = {
  next_runs: string[];
  human_description: string | null;
};
