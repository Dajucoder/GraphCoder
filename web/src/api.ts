/* Transport-agnostic API client.
 * Desktop: window.graphcoder (IPC to app-server child).
 * Web: HTTP JSON-RPC bridge + SSE event stream.
 */

declare global {
  interface Window {
    graphcoder?: {
      request: (method: string, params?: unknown) => Promise<unknown>;
      onNotification: (cb: (method: string, params: Record<string, unknown>) => void) => () => void;
      selectWorkspace: () => Promise<string | null>;
      revealPath: (path: string) => Promise<void>;
      openPath: (path: string) => Promise<string>;
      platform: string;
    };
  }
}

const BASE = "/api/v1";
const native = typeof window !== "undefined" ? window.graphcoder : undefined;

export const isNative = Boolean(native);

async function httpRpc<T = unknown>(
  method: string,
  params: Record<string, unknown> = {}
): Promise<T> {
  const resp = await fetch(`${BASE}/rpc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, params }),
  });
  const data = await resp.json();
  if (!resp.ok || data.error) {
    throw new Error(data.error?.message || `${resp.status} ${resp.statusText}`);
  }
  return data.result as T;
}

export async function rpc<T = unknown>(
  method: string,
  params: Record<string, unknown> = {}
): Promise<T> {
  if (native) return (await native.request(method, params)) as T;
  return httpRpc<T>(method, params);
}

export type Notify = (method: string, params: Record<string, unknown>) => void;

export function subscribeEvents(cb: Notify): () => void {
  if (native) {
    return native.onNotification(cb);
  }
  const es = new EventSource(`${BASE}/stream`);
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data) as { method: string; params: Record<string, unknown> };
      cb(data.method, data.params);
    } catch {
      /* ignore */
    }
  };
  return () => es.close();
}

export const api = {
  initialize: () => rpc<{ capabilities: Record<string, string[]>; defaults: { model: string; provider: string } }>("initialize"),
  listThreads: (includeArchived = false) =>
    rpc<{ threads: ThreadSummary[] }>("threads/list", { include_archived: includeArchived }),
  createThread: (title = "新会话") => rpc<ThreadDetail>("threads/create", { title }),
  getThread: (id: string) => rpc<ThreadDetail & { events: RuntimeEvent[]; tasks: TaskInfo[] }>("threads/get", { thread_id: id }),
  renameThread: (id: string, title: string) => rpc<{ ok: boolean }>("threads/rename", { thread_id: id, title }),
  archiveThread: (id: string, archived = true) => rpc<{ ok: boolean }>("threads/archive", { thread_id: id, archived }),
  forkThread: (id: string) => rpc<ThreadDetail>("threads/fork", { thread_id: id }),
  deleteThread: (id: string) => rpc<{ ok: boolean }>("threads/delete", { thread_id: id }),
  prompt: (id: string, content: string, mode: string) =>
    rpc<{ task: TaskInfo }>("threads/prompt", { thread_id: id, content, mode }),
  resume: (taskId: string) => rpc<{ task: TaskInfo }>("threads/resume", { task_id: taskId }),
  regenerate: (id: string, mode = "chat") =>
    rpc<{ task: TaskInfo }>("threads/regenerate", { thread_id: id, mode }),
  stopTask: (taskId: string) => rpc<{ ok: boolean }>("tasks/stop", { task_id: taskId }),
  exportTask: (taskId: string) => rpc<{ task: TaskInfo; events: RuntimeEvent[]; artifacts: ArtifactInfo[] }>(
    "tasks/export",
    { task_id: taskId }
  ),
  artifactsList: (taskId: string) => rpc<{ artifacts: ArtifactInfo[] }>("artifacts/list", { task_id: taskId }),
  artifactPreview: (path: string) =>
    rpc<{ path: string; content: string; truncated: boolean }>("artifacts/preview", { path }),
  memoryList: (threadId?: string, query = "") =>
    rpc<{ memory: MemoryEntry[] }>("memory/list", { thread_id: threadId || "", query }),
  memoryAdd: (threadId: string, key: string, value: string) =>
    rpc<MemoryEntry>("memory/add", { thread_id: threadId, key, value }),
  memoryDelete: (id: number) => rpc<{ ok: boolean }>("memory/delete", { id }),
  usageStats: (threadId?: string) =>
    rpc<{ input_tokens: number; output_tokens: number; total_tokens: number; cost: number; calls: number; tasks: number }>(
      "usage/stats",
      { thread_id: threadId || "" }
    ),
  listModels: (providerId?: string) => rpc<{ models: ModelInfo[]; active: string }>("models/list", providerId ? { id: providerId } : {}),
  fetchModels: (providerId: string) => rpc<{ provider: ModelInfo; models: ModelInfo[] }>("models/list", { id: providerId }),
  upsertProvider: (provider: ProviderInput) =>
    rpc<ModelInfo>("providers/upsert", { ...provider }),
  deleteProvider: (id: string) => rpc<{ ok: boolean }>("providers/delete", { id }),
  testProvider: (params: Record<string, unknown>) =>
    rpc<ProviderTestResult>("providers/test", params),
  usageDaily: (days = 14) =>
    rpc<{ daily: DailyUsage[]; by_model: ModelUsage[]; today_tasks: number }>("usage/daily", { days }),
  healthSummary: () => rpc<HealthSummary>("health/summary"),
  dataSummary: () => rpc<DataSummary>("data/summary"),
  setOption: (options: Record<string, unknown>) => rpc<{ ok: boolean }>("settings/set", { options }),
  getSettings: () => rpc<SettingsInfo>("settings/get"),
  getWorkspace: () => rpc<WorkspaceInfo>("workspace/get"),
  setWorkspace: (path: string) => rpc<WorkspaceInfo>("workspace/set", { path }),
  listFiles: (path = ".") => rpc<{ path: string; entries: FileEntry[] }>("workspace/files", { path }),
  approve: (id: string, approved: boolean, scope = "once") =>
    rpc<{ ok: boolean }>("approvals/respond", { id, approved, scope }),
  addPermission: (kind: string, pattern: string, action: string) =>
    rpc<{ ok: boolean }>("permissions/add", { kind, pattern, action }),
  listPermissions: () => rpc<{ permissions: PermissionRule[] }>("permissions/list"),
  removePermission: (id: number) => rpc<{ ok: boolean }>("permissions/remove", { id }),
};

export async function chooseWorkspace(): Promise<string | null> {
  return native?.selectWorkspace ? native.selectWorkspace() : null;
}

export async function revealPath(path: string): Promise<void> {
  if (native?.revealPath) await native.revealPath(path);
}

export async function openPath(path: string): Promise<void> {
  if (native?.openPath) await native.openPath(path);
}

export interface ThreadSummary {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  archived: number;
  parent_id?: string | null;
}

export interface ThreadDetail extends ThreadSummary {
  branch_point?: string | null;
}

export interface RuntimeEvent {
  seq: number;
  session_id: string;
  turn_id: string;
  item_id?: string;
  type: string;
  payload: Record<string, unknown>;
  ts: number;
}

export interface TaskInfo {
  id: string;
  session_id: string;
  mode: string;
  status: string;
  content: string;
  created_at: number;
}

export interface ModelInfo {
  id: string;
  name: string;
  kind: string;
  model: string;
  has_key: boolean;
  custom: boolean;
  base_url?: string | null;
  temperature?: number;
  max_tokens?: number;
}

export interface ProviderInput {
  id?: string;
  name: string;
  kind: string;
  model: string;
  base_url?: string;
  api_key?: string;
  api_key_env?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface PermissionRule {
  id: number;
  kind: string;
  pattern: string;
  action: string;
  source: string;
}

export interface ArtifactInfo {
  id: number;
  task_id: string;
  path: string;
  size: number;
  ts: number;
}

export interface MemoryEntry {
  id: number;
  thread_id?: string | null;
  key: string;
  value: string;
  ts: number;
}

export interface ApprovalInfo {
  id: string;
  kind: string;
  target: string;
  reason: string;
  rule_key?: string;
}

export interface WorkspaceInfo {
  path: string;
  name: string;
  branch: string;
  is_git: boolean;
}

export interface FileEntry {
  name: string;
  path: string;
  kind: "file" | "directory";
  size: number;
  updated_at: number;
}

export interface SettingsInfo {
  version?: number;
  active_provider?: string;
  options: Record<string, unknown>;
  permissions: PermissionRule[];
}

export interface ProviderTestResult {
  ok: boolean;
  latency_ms: number;
  detail: string;
  error: string;
}

export interface DailyUsage {
  day: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  calls: number;
}

export interface ModelUsage {
  model: string;
  provider: string;
  tokens: number;
  cost: number;
  calls: number;
}

export interface HealthSummary {
  version: string;
  protocol: string;
  python: string;
  system: string;
  home: string;
  db_path: string;
  db_size: number;
  workspace: string;
  uptime_s: number;
  active_provider: { id: string; name: string; model: string; has_key: boolean };
}

export interface DataSummary {
  home: string;
  db_path: string;
  db_size: number;
  settings_path: string;
  settings_size: number;
  counts: Record<string, number>;
}
