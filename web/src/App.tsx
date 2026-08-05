import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, isNative, subscribeEvents } from "./api";
import type {
  ApprovalInfo,
  ArtifactInfo,
  MemoryEntry,
  ModelInfo,
  RuntimeEvent,
  TaskInfo,
  ThreadDetail,
  ThreadSummary,
} from "./api";

type Module = "chat" | "tasks" | "artifacts" | "memory";

interface UIItem {
  id: string;
  kind: "user_message" | "agent_message" | "tool_call";
  role?: string;
  content?: string;
  name?: string;
  arguments?: Record<string, unknown>;
  result?: string;
  blocked?: boolean;
  running?: boolean;
}

const EMPTY_THREAD: ThreadDetail = {
  id: "",
  title: "",
  created_at: 0,
  updated_at: 0,
  archived: 0,
};

export default function App() {
  const [module, setModule] = useState<Module>("chat");
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [current, setCurrent] = useState<ThreadDetail>(EMPTY_THREAD);
  const [items, setItems] = useState<UIItem[]>([]);
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [usage, setUsage] = useState<{ total_tokens: number; calls: number }>({ total_tokens: 0, calls: 0 });
  const [memory, setMemory] = useState<MemoryEntry[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"chat" | "build">("chat");
  const [busy, setBusy] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [activeModel, setActiveModel] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const itemRef = useRef<Record<string, UIItem>>({});
  const streamRef = useRef<Record<string, string>>({});

  const activeThreads = useMemo(
    () => threads.filter((t) => !t.archived && t.title.toLowerCase().includes(search.toLowerCase())),
    [threads, search]
  );
  const archivedThreads = useMemo(
    () => threads.filter((t) => t.archived && t.title.toLowerCase().includes(search.toLowerCase())),
    [threads, search]
  );

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2600);
  }, []);

  const loadThreads = useCallback(async () => {
    try {
      const data = await api.listThreads();
      setThreads(data.threads);
    } catch {
      setError("无法连接运行时，请确认后端已启动");
    }
  }, []);

  const loadModels = useCallback(async () => {
    try {
      const data = await api.listModels();
      setModels(data.models);
      setActiveModel(data.active);
    } catch {
      /* ignore */
    }
  }, []);

  const refreshForThread = useCallback(async (id: string) => {
    try {
      const data = await api.getThread(id);
      setCurrent(data);
      setTasks(data.tasks || []);
      const usageData = await api.usageStats(id);
      setUsage({ total_tokens: usageData.total_tokens, calls: usageData.calls });
      const mem = await api.memoryList(id);
      setMemory(mem.memory);
      const arts: ArtifactInfo[] = [];
      for (const t of data.tasks || []) {
        const r = await api.artifactsList(t.id);
        arts.push(...r.artifacts);
      }
      setArtifacts(arts);
    } catch {
      /* ignore */
    }
  }, []);

  const openThread = useCallback(async (id: string) => {
    itemRef.current = {};
    streamRef.current = {};
    setBusy(false);
    try {
      const data = await api.getThread(id);
      setCurrent(data);
      setItems(rebuildItems(data.events || []));
      await refreshForThread(id);
    } catch {
      setError("读取会话失败");
    }
  }, [refreshForThread]);

  const refresh = useCallback(async () => {
    await loadThreads();
    if (current.id) await refreshForThread(current.id);
  }, [loadThreads, refreshForThread, current.id]);

  useEffect(() => {
    loadThreads();
    loadModels();
    const unsub = subscribeEvents((method, params) => {
      handleNotification(
        method,
        params,
        setItems,
        itemRef,
        streamRef,
        setBusy,
        setApprovals,
        setError,
        refresh
      );
    });
    return unsub;
  }, [loadThreads, loadModels, refresh]);

  useEffect(() => {
    if (threads.length > 0 && !current.id) {
      openThread(threads[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threads]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [items, busy]);

  const newThread = async () => {
    try {
      const t = await api.createThread();
      await loadThreads();
      await openThread(t.id);
      setModule("chat");
      showToast("已创建新会话");
    } catch {
      setError("创建会话失败");
    }
  };

  const renameThread = async (id: string) => {
    const title = prompt("新会话标题：", threads.find((t) => t.id === id)?.title || "");
    if (title && title.trim()) {
      await api.renameThread(id, title.trim());
      await loadThreads();
    }
  };

  const archiveThread = async (id: string, archived: boolean) => {
    await api.archiveThread(id, archived);
    await loadThreads();
    if (current.id === id && archived) {
      setCurrent(EMPTY_THREAD);
      setItems([]);
      setTasks([]);
    }
  };

  const forkThread = async (id: string) => {
    const t = await api.forkThread(id);
    await loadThreads();
    await openThread(t.id);
    setModule("chat");
    showToast("已创建分支会话");
  };

  const deleteThread = async (id: string) => {
    await api.deleteThread(id);
    await loadThreads();
    if (current.id === id) {
      setCurrent(EMPTY_THREAD);
      setItems([]);
      setTasks([]);
    }
  };

  const regenerate = async () => {
    if (!current.id || busy) return;
    setBusy(true);
    try {
      await api.regenerate(current.id, mode);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  };

  const send = async (contentOverride?: string) => {
    const content = (contentOverride ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setError("");
    let tid = current.id;
    if (!tid) {
      try {
        const t = await api.createThread(content.slice(0, 30));
        tid = t.id;
        await loadThreads();
        setCurrent(t);
      } catch {
        setError("创建会话失败");
        return;
      }
    }
    setItems((prev) => [...prev, { id: `user-${Date.now()}`, kind: "user_message", content }]);
    setBusy(true);
    try {
      await api.prompt(tid, content, mode);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  };

  const respondApproval = async (a: ApprovalInfo, approved: boolean, scope = "once") => {
    await api.approve(a.id, approved, scope);
    setApprovals((prev) => prev.filter((x) => x.id !== a.id));
  };

  const switchModel = async (modelId: string) => {
    await api.setOption({ active_provider: modelId });
    setActiveModel(modelId);
    showToast(`已切换模型: ${modelId}`);
  };

  return (
    <div className={`app ${module !== "chat" ? "no-detail" : ""}`}>
      <ModuleRail module={module} onModule={setModule} onSettings={() => setShowSettings(true)} />
      <SessionPanel
        active={activeThreads}
        archived={archivedThreads}
        currentId={current.id}
        search={search}
        onSearch={setSearch}
        onOpen={(id) => {
          openThread(id);
          setModule("chat");
        }}
        onNew={newThread}
        onRename={renameThread}
        onRegenerate={regenerate}
        onArchive={(id, a) => archiveThread(id, a)}
        onFork={forkThread}
        onDelete={deleteThread}
      />

      <main className="main">
        {module === "chat" && (
          <ChatView
            thread={current}
            items={items}
            busy={busy}
            approvals={approvals}
            error={error}
            input={input}
            mode={mode}
            models={models}
            activeModel={activeModel}
            onInput={setInput}
            onSend={send}
            onMode={setMode}
            onModel={switchModel}
            onApprove={respondApproval}
            onCloseError={() => setError("")}
            listRef={listRef}
            onRegenerate={regenerate}
          />
        )}
        {module === "tasks" && <TasksView tasks={tasks} usage={usage} onExport={exportTask} />}
        {module === "artifacts" && <ArtifactsView artifacts={artifacts} threadId={current.id} />}
        {module === "memory" && (
          <MemoryView memory={memory} threadId={current.id} onChanged={refreshForThread} showToast={showToast} />
        )}
      </main>

      {module === "chat" && (
        <DetailPanel items={items} tasks={tasks} usage={usage} artifacts={artifacts} />
      )}

      {showSettings && (
        <SettingsDrawer models={models} activeModel={activeModel} onModel={switchModel} onClose={() => setShowSettings(false)} />
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

async function exportTask(task: TaskInfo) {
  const data = await api.exportTask(task.id);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `graphcoder-task-${task.id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ============================== 模块导航 ============================== */
function ModuleRail(props: {
  module: Module;
  onModule: (m: Module) => void;
  onSettings: () => void;
}) {
  const items: { key: Module; icon: string; label: string }[] = [
    { key: "chat", icon: "💬", label: "会话" },
    { key: "tasks", icon: "📋", label: "任务" },
    { key: "artifacts", icon: "📦", label: "产物" },
    { key: "memory", icon: "🧠", label: "记忆" },
  ];
  return (
    <nav className="module-rail">
      <div className="rail-logo">◉</div>
      {items.map((it) => (
        <button
          key={it.key}
          className={`rail-item ${props.module === it.key ? "active" : ""}`}
          title={it.label}
          onClick={() => props.onModule(it.key)}
        >
          <span className="rail-icon">{it.icon}</span>
          <span className="rail-label">{it.label}</span>
        </button>
      ))}
      <div className="rail-spacer" />
      <button className="rail-item" title="设置与权限" onClick={props.onSettings}>
        <span className="rail-icon">⚙</span>
        <span className="rail-label">设置</span>
      </button>
    </nav>
  );
}

/* ============================== 会话面板 ============================== */
function SessionPanel(props: {
  active: ThreadSummary[];
  archived: ThreadSummary[];
  currentId: string;
  search: string;
  onSearch: (s: string) => void;
  onOpen: (id: string) => void;
  onNew: () => void;
  onRename: (id: string) => void;
  onRegenerate: () => void;
  onArchive: (id: string, archived: boolean) => void;
  onFork: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="logo">◉</span> GraphCoder
      </div>
      <button className="new-btn" onClick={props.onNew}>
        ＋ 新会话
      </button>
      <input
        className="search"
        value={props.search}
        onChange={(e) => props.onSearch(e.target.value)}
        placeholder="搜索会话…"
      />
      <div className="section-header">
        <h3 className="section-header-title section-header-title-accent">会话</h3>
        <span className="section-header-count">{props.active.length}</span>
      </div>
      <div className="session-list">
        {props.active.map((t) => (
          <SessionRow
            key={t.id}
            thread={t}
            currentId={props.currentId}
            onOpen={props.onOpen}
            onRename={props.onRename}
            onRegenerate={props.onRegenerate}
            onArchive={props.onArchive}
            onFork={props.onFork}
            onDelete={props.onDelete}
          />
        ))}
        {props.active.length === 0 && (
          <div className="composer-hint" style={{ padding: "8px 6px" }}>
            暂无会话，点击「新会话」开始
          </div>
        )}
      </div>
      {props.archived.length > 0 && (
        <>
          <div className="section-header">
            <h3 className="section-header-title">已归档</h3>
            <span className="section-header-count">{props.archived.length}</span>
          </div>
          <div className="session-list" style={{ flex: "0 1 auto", maxHeight: "28%" }}>
            {props.archived.map((t) => (
              <SessionRow
                key={t.id}
                thread={t}
                currentId={props.currentId}
                onOpen={props.onOpen}
                onRename={props.onRename}
                onRegenerate={props.onRegenerate}
                onArchive={props.onArchive}
                onFork={props.onFork}
                onDelete={props.onDelete}
              />
            ))}
          </div>
        </>
      )}
      <div className="sidebar-footer">
        <span className="permission-pill ask" title="权限策略：ask 询问">
          <span className="dot" /> ask 审批
        </span>
      </div>
    </aside>
  );
}

function SessionRow(props: {
  thread: ThreadSummary;
  currentId: string;
  onOpen: (id: string) => void;
  onRename: (id: string) => void;
  onRegenerate: () => void;
  onArchive: (id: string, archived: boolean) => void;
  onFork: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const t = props.thread;
  return (
    <div
      className={`session-item ${t.id === props.currentId ? "active" : ""} ${t.archived ? "archived" : ""}`}
      onClick={() => props.onOpen(t.id)}
    >
      <span className="sess-title">{t.title}</span>
      <span className="sess-time">{relTime(t.updated_at)}</span>
      <span className="session-actions">
        <button className="mini" title="重命名" onClick={(e) => { e.stopPropagation(); props.onRename(t.id); }}>✎</button>
        {t.id === props.currentId && (
          <button className="mini" title="重新生成" onClick={(e) => { e.stopPropagation(); props.onRegenerate(); }}>↻</button>
        )}
        <button className="mini" title="分支" onClick={(e) => { e.stopPropagation(); props.onFork(t.id); }}>⑂</button>
        <button className="mini" title={t.archived ? "取消归档" : "归档"} onClick={(e) => { e.stopPropagation(); props.onArchive(t.id, !t.archived); }}>
          {t.archived ? "↩" : "🗄"}
        </button>
        <button className="mini del" title="删除" onClick={(e) => { e.stopPropagation(); if (confirm(`删除会话「${t.title}」？`)) props.onDelete(t.id); }}>×</button>
      </span>
    </div>
  );
}

/* ============================== 聊天视图 ============================== */
function ChatView(props: {
  thread: ThreadDetail;
  items: UIItem[];
  busy: boolean;
  approvals: ApprovalInfo[];
  error: string;
  input: string;
  mode: "chat" | "build";
  models: ModelInfo[];
  activeModel: string;
  onInput: (s: string) => void;
  onSend: (content?: string) => void;
  onMode: (m: "chat" | "build") => void;
  onModel: (id: string) => void;
  onApprove: (a: ApprovalInfo, approved: boolean, scope?: string) => void;
  onCloseError: () => void;
  listRef: React.RefObject<HTMLDivElement>;
  onRegenerate: () => void;
}) {
  return (
    <>
      <header className="workbar">
        <div className="workbar-title">
          <span className="workbar-eyebrow">工作区 · {isNative ? "Desktop" : "Web"}</span>
          <h2>{props.thread.title || "GraphCoder"}</h2>
        </div>
        <div className="workbar-actions">
          <select
            className="model-select"
            value={props.activeModel}
            onChange={(e) => props.onModel(e.target.value)}
            title="切换模型 Provider"
          >
            {props.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} · {m.model || "默认模型"}
              </option>
            ))}
          </select>
          <div className="mode-switch">
            <button className={props.mode === "chat" ? "active" : ""} onClick={() => props.onMode("chat")}>
              聊天
            </button>
            <button className={props.mode === "build" ? "active" : ""} onClick={() => props.onMode("build")}>
              构建
            </button>
          </div>
        </div>
      </header>

      <div className="messages" ref={props.listRef}>
        {props.items.length === 0 && (
          <div className="empty">
            <h1>GraphCoder</h1>
            <p>
              多 Agent 编程助手 · 自研引擎 · {isNative ? "桌面 IPC" : "Web 传输"}
              <br />
              {props.mode === "chat"
                ? "聊天模式：提问或让我直接读写代码、运行命令（危险命令需审批）。"
                : "构建模式：PM → 架构 → 编码 → 审查 → QA 全流程。"}
            </p>
          </div>
        )}
        {props.items.map((it) => (
          <ItemView key={it.id} item={it} />
        ))}
        {props.busy && (
          <div className="turn-processing">
            <span className="turn-processing-spinner" />
            正在运行{props.mode === "build" ? "构建流水线" : ""}…
          </div>
        )}
      </div>

      {props.approvals.length > 0 && (
        <div className="approval-bar">
          <div className="approval-info">
            <b>⏸ 等待审批（{props.approvals[0].kind}）</b>
            <code>{props.approvals[0].target}</code>
            <span className="reason">{props.approvals[0].reason}</span>
          </div>
          <div className="approval-actions">
            <button className="btn" onClick={() => props.onApprove(props.approvals[0], true, "always")}>
              始终允许
            </button>
            <button className="btn success" onClick={() => props.onApprove(props.approvals[0], true)}>
              允许
            </button>
            <button className="btn danger" onClick={() => props.onApprove(props.approvals[0], false)}>
              拒绝
            </button>
          </div>
        </div>
      )}

      {props.error && (
        <div className="error-bar">
          <span>{props.error}</span>
          <button className="mini del" onClick={props.onCloseError}>
            关闭
          </button>
        </div>
      )}

      <footer className="composer">
        <div className="composer-main">
          <textarea
            value={props.input}
            onChange={(e) => props.onInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                props.onSend();
              }
            }}
            placeholder={
              props.mode === "chat"
                ? "输入消息，回车发送（Shift+Enter 换行）"
                : "描述你要构建的项目，例如：写一个 FastAPI 待办应用"
            }
            rows={2}
            disabled={props.busy}
          />
          <span className="composer-hint">
            {props.mode === "build"
              ? "构建模式：PM → 架构 → 编码 → 审查 → QA"
              : "聊天模式 · 工具调用需审批"}
          </span>
        </div>
        <button className="send" onClick={() => props.onSend()} disabled={props.busy || !props.input.trim()}>
          发送
        </button>
        {props.items.some((i) => i.kind === "user_message") && !props.busy && (
          <button className="send ghost" onClick={props.onRegenerate} title="重新生成上一轮">
            重新生成
          </button>
        )}
      </footer>
    </>
  );
}

/* ============================== 回合项 ============================== */
function ItemView({ item }: { item: UIItem }) {
  if (item.kind === "user_message") {
    return (
      <div className="turn turn-user">
        <div className="md"><Markdown text={item.content || ""} /></div>
      </div>
    );
  }
  if (item.kind === "tool_call") {
    return <ToolCard item={item} />;
  }
  return (
    <div className="turn turn-assistant">
      <div className="agent-identity">{item.role || "assistant"}</div>
      {item.content ? (
        <div className={`md ${item.running ? "turn-streaming" : ""}`}>
          <Markdown text={item.content} />
        </div>
      ) : (
        <span className="typing">正在思考…</span>
      )}
    </div>
  );
}

function ToolCard({ item }: { item: UIItem }) {
  const [open, setOpen] = useState(false);
  const status = item.blocked ? "blocked" : item.running ? "running" : "ok";
  const label = status === "running" ? "运行中" : status === "blocked" ? "已阻止" : "完成";
  return (
    <div className="tool-call">
      <div className="tool-call-header" onClick={() => setOpen(!open)}>
        <span className="tool-icon">⚙</span>
        <span className="tool-name">{item.name}</span>
        <span className={`tool-status ${status}`}>{label}</span>
        <span className="tool-chevron">{open ? "▾" : "▸"}</span>
      </div>
      {open && item.arguments && Object.keys(item.arguments).length > 0 && (
        <pre className="tool-args">{JSON.stringify(item.arguments, null, 2)}</pre>
      )}
      {open && item.result && (
        <pre className="tool-result">{item.result.slice(0, 1200)}</pre>
      )}
    </div>
  );
}

function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
        code: ({ children, ...props }) => (
          <code className="inline-code" {...props}>
            {children}
          </code>
        ),
        pre: ({ children }) => <pre className="md-pre">{children}</pre>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

/* ============================== 右侧详情面板 ============================== */
function DetailPanel({
  items,
  tasks,
  usage,
  artifacts,
}: {
  items: UIItem[];
  tasks: TaskInfo[];
  usage: { total_tokens: number; calls: number };
  artifacts: ArtifactInfo[];
}) {
  const completed = tasks.filter((t) => t.status === "completed").length;
  const running = tasks.filter((t) => t.status === "running" || t.status === "pending").length;
  const failed = tasks.filter((t) => t.status === "error" || t.status === "cancelled").length;
  const activeRole = useMemo(() => {
    for (let i = items.length - 1; i >= 0; i--) {
      const it = items[i];
      if (it.kind === "agent_message" && it.role && it.role !== "assistant") return it.role;
    }
    return null;
  }, [items]);

  return (
    <aside className="detail-panel">
      <div className="section-header">
        <h3 className="section-header-title section-header-title-accent">任务账本</h3>
        <span className="section-header-count">{tasks.length}</span>
      </div>
      <div className="stat-grid">
        <StatTile value={completed} label="已完成" tone={completed ? "success" : ""} />
        <StatTile value={running} label="运行中" tone={running ? "running" : ""} />
        <StatTile value={failed} label="失败" tone={failed ? "destructive" : ""} />
        <StatTile value={usage.total_tokens} label="Tokens" />
      </div>
      <div className="task-list">
        {tasks.slice(0, 5).map((t) => (
          <div key={t.id} className="task-card">
            <div className="task-card-top">
              <span className="task-mode">{t.mode}</span>
              <span className={`status-pill ${t.status}`}>{t.status}</span>
            </div>
            <p className="task-content">{t.content}</p>
          </div>
        ))}
        {tasks.length === 0 && <div className="composer-hint">暂无任务</div>}
      </div>

      <div className="section-header">
        <h3 className="section-header-title">构建图</h3>
      </div>
      <AgentGraph activeRole={activeRole} />

      <div className="section-header">
        <h3 className="section-header-title">本次产物</h3>
        <span className="section-header-count">{artifacts.length}</span>
      </div>
      <div className="file-chips">
        {artifacts.map((a) => (
          <code key={a.id} className="file-chip">
            {a.path}
          </code>
        ))}
        {artifacts.length === 0 && <div className="composer-hint">Agent 写入的文件会出现在这里</div>}
      </div>
    </aside>
  );
}

function StatTile({ value, label, tone }: { value: number | string; label: string; tone?: string }) {
  return (
    <div className="stat-tile">
      <span className={`stat-tile-value ${tone || ""}`}>{value}</span>
      <span className="stat-tile-label">{label}</span>
    </div>
  );
}

function AgentGraph({ activeRole }: { activeRole: string | null }) {
  const roles = [
    { key: "pm", label: "PM" },
    { key: "architect", label: "架构" },
    { key: "developer", label: "编码" },
    { key: "reviewer", label: "审查" },
    { key: "qa", label: "QA" },
  ];
  return (
    <div className="agent-graph">
      {roles.map((r, i) => (
        <div key={r.key} className="graph-row">
          <span className={`graph-node ${activeRole === r.key ? "active" : ""}`}>{r.label}</span>
          {i < roles.length - 1 && <span className="graph-arrow">→</span>}
        </div>
      ))}
    </div>
  );
}

/* ============================== 任务视图 ============================== */
function TasksView({
  tasks,
  usage,
  onExport,
}: {
  tasks: TaskInfo[];
  usage: { total_tokens: number; calls: number };
  onExport: (t: TaskInfo) => void;
}) {
  const completed = tasks.filter((t) => t.status === "completed").length;
  const running = tasks.filter((t) => t.status === "running" || t.status === "pending").length;
  const failed = tasks.filter((t) => t.status === "error" || t.status === "cancelled").length;
  return (
    <div className="module-view">
      <div className="page-header">
        <h2>任务账本</h2>
        <p>所有回合的持久化记录：预算、状态、用量与导出</p>
      </div>
      <div className="stat-grid stat-grid-wide">
        <StatTile value={completed} label="已完成" tone={completed ? "success" : ""} />
        <StatTile value={running} label="运行中" tone={running ? "running" : ""} />
        <StatTile value={failed} label="失败" tone={failed ? "destructive" : ""} />
        <StatTile value={usage.calls} label="调用次数" />
        <StatTile value={usage.total_tokens} label="Tokens" />
      </div>
      <div className="task-list task-list-wide">
        {tasks.map((t) => (
          <div key={t.id} className="task-card task-card-wide">
            <div className="task-card-top">
              <span className="task-mode">{t.mode}</span>
              <span className={`status-pill ${t.status}`}>{t.status}</span>
              <span className="sess-time">{new Date(t.created_at * 1000).toLocaleString("zh-CN")}</span>
              <button className="mini" title="导出 JSON" onClick={() => onExport(t)}>
                导出
              </button>
            </div>
            <p className="task-content">{t.content}</p>
          </div>
        ))}
        {tasks.length === 0 && <div className="composer-hint">暂无任务</div>}
      </div>
    </div>
  );
}

/* ============================== 产物视图 ============================== */
function ArtifactsView({ artifacts, threadId }: { artifacts: ArtifactInfo[]; threadId: string }) {
  const [preview, setPreview] = useState<{ path: string; content: string; truncated: boolean } | null>(null);
  const open = async (path: string) => {
    try {
      setPreview(await api.artifactPreview(path));
    } catch {
      setPreview({ path, content: "(无法读取文件内容)", truncated: false });
    }
  };
  return (
    <div className="module-view artifacts-view">
      <div className="page-header">
        <h2>产物</h2>
        <p>Agent 写入的文件（会话 {threadId || "—"}）</p>
      </div>
      <div className="artifact-list">
        {artifacts.map((a) => (
          <button key={a.id} className="artifact-row" onClick={() => open(a.path)}>
            <span className="artifact-path">📄 {a.path}</span>
            <span className="sess-time">{fmtSize(a.size)}</span>
          </button>
        ))}
        {artifacts.length === 0 && <div className="composer-hint">暂无产物</div>}
      </div>
      {preview && (
        <div className="artifact-preview">
          <div className="artifact-preview-head">
            <b>{preview.path}</b>
            <button className="mini del" onClick={() => setPreview(null)}>×</button>
          </div>
          <pre className="artifact-content">{preview.content}</pre>
        </div>
      )}
    </div>
  );
}

/* ============================== 记忆视图 ============================== */
function MemoryView({
  memory,
  threadId,
  onChanged,
  showToast,
}: {
  memory: MemoryEntry[];
  threadId: string;
  onChanged: (id: string) => void;
  showToast: (s: string) => void;
}) {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const add = async () => {
    if (!key.trim() || !value.trim()) return;
    await api.memoryList(threadId); // touch
    showToast("请通过 Agent 的 memory_write 工具写入记忆");
  };
  return (
    <div className="module-view">
      <div className="page-header">
        <h2>记忆</h2>
        <p>会话长期记忆：Agent 可通过 memory_write / memory_read / memory_forget 工具访问</p>
      </div>
      <div className="memory-add">
        <input className="search" placeholder="key" value={key} onChange={(e) => setKey(e.target.value)} />
        <input className="search" placeholder="value" value={value} onChange={(e) => setValue(e.target.value)} />
        <button className="btn" onClick={add}>写入</button>
      </div>
      <div className="memory-list">
        {memory.map((m) => (
          <div key={m.id} className="memory-row">
            <div className="memory-main">
              <b>{m.key}</b>
              <span className="composer-hint">{m.value}</span>
            </div>
            <button
              className="mini del"
              onClick={async () => {
                await api.memoryDelete(m.id);
                onChanged(threadId);
              }}
            >
              删除
            </button>
          </div>
        ))}
        {memory.length === 0 && <div className="composer-hint">暂无记忆</div>}
      </div>
    </div>
  );
}

/* ============================== 设置 ============================== */
function SettingsDrawer({
  models,
  activeModel,
  onModel,
  onClose,
}: {
  models: ModelInfo[];
  activeModel: string;
  onModel: (id: string) => void;
  onClose: () => void;
}) {
  const [permissions, setPermissions] = useState<{ id: number; kind: string; pattern: string; action: string }[]>([]);
  const [form, setForm] = useState({ kind: "command", pattern: "", action: "ask" });

  useEffect(() => {
    api.listPermissions().then((r) => setPermissions(r.permissions)).catch(() => {});
  }, []);

  const addRule = async () => {
    if (!form.pattern) return;
    await api.addPermission(form.kind, form.pattern, form.action);
    const r = await api.listPermissions();
    setPermissions(r.permissions);
    setForm({ ...form, pattern: "" });
  };

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h2>设置与权限</h2>
          <button className="del" onClick={onClose}>×</button>
        </div>
        <h3>模型 Provider</h3>
        <div className="model-list">
          {models.map((m) => (
            <div key={m.id} className={`provider-row ${m.id === activeModel ? "active" : ""}`}>
              <div>
                <b>{m.name}</b>
                <span className="composer-hint">
                  {" "}
                  · {m.kind} · {m.model || "默认"}
                </span>
              </div>
              <button className="btn" disabled={m.id === activeModel} onClick={() => onModel(m.id)}>
                {m.id === activeModel ? "使用中" : "使用"}
              </button>
            </div>
          ))}
        </div>
        <h3>权限策略（allow / ask / deny）</h3>
        <div className="form">
          <label>
            类型
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <option value="command">命令模式</option>
              <option value="tool">工具名</option>
              <option value="dir">目录前缀</option>
            </select>
          </label>
          <label>
            模式
            <input
              value={form.pattern}
              onChange={(e) => setForm({ ...form, pattern: e.target.value })}
              placeholder="如 git push* / rm -rf / write_file / src/"
            />
          </label>
          <label>
            动作
            <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>
              <option value="allow">allow 放行</option>
              <option value="ask">ask 询问</option>
              <option value="deny">deny 拒绝</option>
            </select>
          </label>
        </div>
        <div className="drawer-actions">
          <button className="btn primary" onClick={addRule}>
            添加策略
          </button>
        </div>
        <div className="permission-list">
          {permissions.map((p) => (
            <div key={p.id} className="permission-row">
              <span className={`action-chip ${p.action}`}>{p.action}</span>
              <span>
                {p.kind}: <code>{p.pattern}</code>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ============================== 事件处理 ============================== */
function handleNotification(
  method: string,
  params: Record<string, unknown>,
  setItems: React.Dispatch<React.SetStateAction<UIItem[]>>,
  itemRef: React.MutableRefObject<Record<string, UIItem>>,
  streamRef: React.MutableRefObject<Record<string, string>>,
  setBusy: (b: boolean) => void,
  setApprovals: React.Dispatch<React.SetStateAction<ApprovalInfo[]>>,
  setError: (e: string) => void,
  refresh: () => void
) {
  const id = String(params.item_id || "");
  const kind = String(params.kind || "");
  if (method === "item/started") {
    if (kind === "tool_call") {
      const item: UIItem = {
        id,
        kind: "tool_call",
        name: String(params.name || "tool"),
        arguments: (params.arguments as Record<string, unknown>) || {},
        running: true,
      };
      itemRef.current[id] = item;
      setItems((prev) => [...prev, item]);
    } else if (kind === "agent_message") {
      const item: UIItem = {
        id,
        kind: "agent_message",
        role: String(params.role || "assistant"),
        content: "",
        running: true,
      };
      itemRef.current[id] = item;
      streamRef.current[id] = "";
      setItems((prev) => [...prev, item]);
    }
  } else if (method === "item/delta") {
    const sid = id || Object.keys(streamRef.current).pop() || "";
    streamRef.current[sid] = (streamRef.current[sid] || "") + String(params.delta || "");
    const item = itemRef.current[sid];
    if (item) {
      item.content = streamRef.current[sid];
      setItems((prev) => [...prev.slice(0, -1), item]);
    }
  } else if (method === "item/completed") {
    const payload = (params.payload as Record<string, unknown>) || {};
    const item = itemRef.current[id];
    if (kind === "user_message") {
      if (!item) {
        const ui: UIItem = { id, kind: "user_message", content: String(payload.content || "") };
        itemRef.current[id] = ui;
        setItems((prev) => [...prev, ui]);
      }
    } else if (kind === "agent_message") {
      if (item) {
        item.content = String(payload.content ?? streamRef.current[id] ?? "");
        item.running = false;
        setItems((prev) => {
          const idx = prev.findIndex((x) => x.id === id);
          if (idx >= 0) return [...prev.slice(0, idx), item, ...prev.slice(idx + 1)];
          return [...prev, item];
        });
      } else {
        setItems((prev) => [
          ...prev,
          { id, kind: "agent_message", content: String(payload.content || ""), running: false },
        ]);
      }
    } else if (kind === "tool_call" && item) {
      item.running = false;
      item.blocked = Boolean(payload.blocked);
      item.result = payload.result ? String(payload.result) : undefined;
      setItems((prev) => prev.map((x) => (x.id === id ? item : x)));
    }
  } else if (method === "approval/requested") {
    setApprovals((prev) => [
      ...prev.filter((a) => a.id !== String(params.id)),
      {
        id: String(params.id),
        kind: String(params.kind || "tool"),
        target: String(params.target || ""),
        reason: String(params.reason || ""),
      },
    ]);
  } else if (method === "turn/started") {
    setBusy(true);
  } else if (method === "turn/completed") {
    setBusy(false);
    refresh();
  } else if (method === "error") {
    setError(String(params.message || "任务出错"));
    setBusy(false);
  }
}

function rebuildItems(events: RuntimeEvent[]): UIItem[] {
  const items: UIItem[] = [];
  const map: Record<string, UIItem> = {};
  for (const ev of events) {
    const p = ev.payload;
    const inner = (p.payload as Record<string, unknown>) || {};
    const kind = String(p.kind || "");
    const id = String(ev.item_id || `${ev.seq}`);
    if (ev.type === "item/started") {
      if (kind === "tool_call") {
        const it: UIItem = {
          id,
          kind: "tool_call",
          name: String(p.name || "tool"),
          arguments: (p.arguments as Record<string, unknown>) || {},
        };
        map[id] = it;
        items.push(it);
      } else if (kind === "agent_message") {
        const it: UIItem = { id, kind: "agent_message", role: String(p.role || "assistant"), content: "" };
        map[id] = it;
        items.push(it);
      }
    } else if (ev.type === "item/completed") {
      if (kind === "user_message") {
        items.push({ id, kind: "user_message", content: String(inner.content || "") });
      } else if (kind === "agent_message") {
        const existing = map[id];
        if (existing) {
          existing.content = String(inner.content || "");
        } else {
          items.push({ id, kind: "agent_message", content: String(inner.content || "") });
        }
      } else if (kind === "tool_call" && map[id]) {
        map[id].running = false;
        map[id].blocked = Boolean(inner.blocked);
        map[id].result = inner.result ? String(inner.result) : undefined;
      }
    }
  }
  return items;
}

function relTime(ts: number): string {
  const s = Math.floor(Date.now() / 1000 - ts);
  if (s < 60) return "刚刚";
  if (s < 3600) return `${Math.floor(s / 60)}分`;
  if (s < 86400) return `${Math.floor(s / 3600)}时`;
  return `${Math.floor(s / 86400)}天`;
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}
