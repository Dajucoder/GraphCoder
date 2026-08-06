import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  ArchiveRestore,
  Bot,
  Box,
  Brain,
  ChevronDown,
  ChevronRight,
  CircleStop,
  Code2,
  ExternalLink,
  File,
  FileCode2,
  Folder,
  FolderGit2,
  GitBranch,
  History,
  ListTodo,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Paperclip,
  Plus,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Split,
  Trash2,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  api,
  chooseWorkspace,
  isNative,
  openPath,
  revealPath,
  subscribeEvents,
} from "./api";
import type {
  ApprovalInfo,
  ArtifactInfo,
  FileEntry,
  MemoryEntry,
  ModelInfo,
  RuntimeEvent,
  SettingsInfo,
  TaskInfo,
  ThreadDetail,
  ThreadSummary,
  WorkspaceInfo,
} from "./api";
import SettingsSurface, { type Theme } from "./SettingsSurface";
import { EmptyPanel, IconButton, MemoryManager, PageHeading } from "./widgets";

type View = "chat" | "tasks" | "artifacts" | "memory";
type WorkbarTab = "tasks" | "files" | "activity";

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
  streamDirty?: boolean;
}

const EMPTY_THREAD: ThreadDetail = {
  id: "",
  title: "",
  created_at: 0,
  updated_at: 0,
  archived: 0,
};

const EMPTY_WORKSPACE: WorkspaceInfo = {
  path: "",
  name: "选择项目",
  branch: "",
  is_git: false,
};

const STARTERS = [
  "帮我梳理这个项目的架构",
  "检查当前代码中可能存在的问题",
  "实现一个功能并补充测试",
];

export default function App() {
  const [view, setView] = useState<View>("chat");
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [current, setCurrent] = useState<ThreadDetail>(EMPTY_THREAD);
  const [items, setItems] = useState<UIItem[]>([]);
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
  const [memory, setMemory] = useState<MemoryEntry[]>([]);
  const [usage, setUsage] = useState({ total_tokens: 0, calls: 0, cost: 0 });
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [activeModel, setActiveModel] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceInfo>(EMPTY_WORKSPACE);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"chat" | "build">("chat");
  const [busy, setBusy] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalInfo[]>([]);
  const [search, setSearch] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [workbarOpen, setWorkbarOpen] = useState(true);
  const [workbarTab, setWorkbarTab] = useState<WorkbarTab>("tasks");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<SettingsInfo | null>(null);
  const [theme, setTheme] = useState<Theme>(() => {
    return (localStorage.getItem("graphcoder-theme") as Theme) || "light";
  });
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const itemRef = useRef<Record<string, UIItem>>({});
  const streamRef = useRef<Record<string, string>>({});
  const currentIdRef = useRef("");

  const activeThreads = useMemo(
    () => threads.filter((thread) => !thread.archived && matches(thread.title, search)),
    [threads, search],
  );
  const archivedThreads = useMemo(
    () => threads.filter((thread) => thread.archived && matches(thread.title, search)),
    [threads, search],
  );
  const runningTask = tasks.find((task) => ["pending", "running"].includes(task.status));

  const showToast = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  }, []);

  const loadThreads = useCallback(async () => {
    const data = await api.listThreads(true);
    setThreads(data.threads);
    return data.threads;
  }, []);

  const refreshThreadData = useCallback(async (threadId: string) => {
    if (!threadId) return;
    const [detail, usageData, memoryData] = await Promise.all([
      api.getThread(threadId),
      api.usageStats(threadId),
      api.memoryList(threadId),
    ]);
    if (currentIdRef.current && currentIdRef.current !== threadId) return;
    setCurrent(detail);
    setTasks(detail.tasks || []);
    setUsage({
      total_tokens: usageData.total_tokens,
      calls: usageData.calls,
      cost: usageData.cost,
    });
    setMemory(memoryData.memory);
    const artifactGroups = await Promise.all(
      (detail.tasks || []).map((task) => api.artifactsList(task.id)),
    );
    setArtifacts(artifactGroups.flatMap((group) => group.artifacts));
  }, []);

  const openThread = useCallback(async (threadId: string) => {
    currentIdRef.current = threadId;
    itemRef.current = {};
    streamRef.current = {};
    setBusy(false);
    setApprovals([]);
    setError("");
    try {
      const detail = await api.getThread(threadId);
      if (currentIdRef.current !== threadId) return;
      setCurrent(detail);
      setItems(rebuildItems(detail.events || []));
      await refreshThreadData(threadId);
      setView("chat");
    } catch (reason) {
      setError(errorMessage(reason, "读取会话失败"));
    }
  }, [refreshThreadData]);

  const bootstrap = useCallback(async () => {
    try {
      const [, threadData, modelData, workspaceData, settingsData] = await Promise.all([
        api.initialize(),
        api.listThreads(true),
        api.listModels(),
        api.getWorkspace(),
        api.getSettings(),
      ]);
      setThreads(threadData.threads);
      setModels(modelData.models);
      setActiveModel(modelData.active);
      setWorkspace(workspaceData);
      setSettings(settingsData);
      const defaultMode = settingsData.options.default_mode;
      if (defaultMode === "build" || defaultMode === "chat") setMode(defaultMode);
      const first = threadData.threads.find((thread) => !thread.archived);
      if (first && !currentIdRef.current) await openThread(first.id);
    } catch (reason) {
      setError(errorMessage(reason, "无法连接 GraphCoder Runtime"));
    }
  }, [openThread]);

  useEffect(() => {
    bootstrap();
    const unsubscribe = subscribeEvents((method, params) => {
      if (method === "server/error") {
        setError(String(params.message || "GraphCoder Runtime 不可用"));
        setBusy(false);
        return;
      }
      if (method === "workspace/changed") {
        setWorkspace(params as unknown as WorkspaceInfo);
        return;
      }
      const eventThreadId = String(params.thread_id || params.session_id || "");
      if (
        eventThreadId &&
        currentIdRef.current &&
        eventThreadId !== currentIdRef.current
      ) {
        if (method === "turn/completed") void loadThreads();
        return;
      }
      handleNotification(method, params, {
        setItems,
        itemRef,
        streamRef,
        setBusy,
        setApprovals,
        setError,
        onSettled: async () => {
          await loadThreads();
          if (currentIdRef.current) await refreshThreadData(currentIdRef.current);
        },
      });
    });
    return unsubscribe;
  }, [bootstrap, loadThreads, refreshThreadData]);

  useEffect(() => {
    const root = document.documentElement;
    localStorage.setItem("graphcoder-theme", theme);
    if (theme !== "system") {
      root.dataset.theme = theme;
      return;
    }
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      root.dataset.theme = query.matches ? "dark" : "light";
    };
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, [theme]);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [items, busy]);

  const newThread = async () => {
    try {
      const thread = await api.createThread();
      await loadThreads();
      await openThread(thread.id);
      showToast("已创建新会话");
    } catch (reason) {
      setError(errorMessage(reason, "创建会话失败"));
    }
  };

  const send = async (override?: string) => {
    const content = (override ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setError("");
    let threadId = current.id;
    if (!threadId) {
      try {
        const thread = await api.createThread(content.slice(0, 32));
        threadId = thread.id;
        currentIdRef.current = thread.id;
        setCurrent(thread);
        await loadThreads();
      } catch (reason) {
        setError(errorMessage(reason, "创建会话失败"));
        return;
      }
    }
    setItems((previous) => [
      ...previous,
      { id: `local-user-${Date.now()}`, kind: "user_message", content },
    ]);
    setBusy(true);
    try {
      await api.prompt(threadId, content, mode);
    } catch (reason) {
      setError(errorMessage(reason, "发送失败"));
      setBusy(false);
    }
  };

  const switchWorkspace = async () => {
    let selected = await chooseWorkspace();
    if (!selected && !isNative) selected = window.prompt("输入项目绝对路径", workspace.path) || null;
    if (!selected) return;
    try {
      const next = await api.setWorkspace(selected);
      setWorkspace(next);
      showToast(`已切换到 ${next.name}`);
    } catch (reason) {
      setError(errorMessage(reason, "切换项目失败"));
    }
  };

  const switchModel = async (providerId: string) => {
    try {
      await api.setOption({ active_provider: providerId });
      setActiveModel(providerId);
      showToast(`已切换模型: ${models.find((model) => model.id === providerId)?.name || providerId}`);
    } catch (reason) {
      setError(errorMessage(reason, "切换模型失败"));
    }
  };

  const refreshModels = async () => {
    const data = await api.listModels();
    setModels(data.models);
    setActiveModel(data.active);
  };

  const archiveThread = async (threadId: string, archived: boolean) => {
    await api.archiveThread(threadId, archived);
    await loadThreads();
    if (current.id === threadId && archived) {
      currentIdRef.current = "";
      setCurrent(EMPTY_THREAD);
      setItems([]);
      setTasks([]);
      setArtifacts([]);
    }
  };

  const deleteThread = async (threadId: string) => {
    if (!window.confirm("确定删除这个会话及其历史记录吗？")) return;
    await api.deleteThread(threadId);
    const next = await loadThreads();
    if (current.id === threadId) {
      const first = next.find((thread) => !thread.archived);
      if (first) await openThread(first.id);
      else {
        currentIdRef.current = "";
        setCurrent(EMPTY_THREAD);
        setItems([]);
      }
    }
  };

  const renameThread = async (thread: ThreadSummary) => {
    const title = window.prompt("重命名会话", thread.title)?.trim();
    if (!title) return;
    await api.renameThread(thread.id, title);
    await loadThreads();
    if (current.id === thread.id) setCurrent((value) => ({ ...value, title }));
  };

  const forkThread = async (threadId: string) => {
    const fork = await api.forkThread(threadId);
    await loadThreads();
    await openThread(fork.id);
    showToast("已创建分支会话");
  };

  const openSettings = async () => {
    setSettingsOpen(true);
    try {
      setSettings(await api.getSettings());
    } catch {
      // Existing settings remain usable while the refresh error is shown elsewhere.
    }
  };

  return (
    <div className="app-frame" data-sidebar={sidebarCollapsed ? "collapsed" : "expanded"}>
      <div className="window-drag-region" />
      <Sidebar
        collapsed={sidebarCollapsed}
        view={view}
        threads={activeThreads}
        archivedThreads={archivedThreads}
        currentId={current.id}
        search={search}
        workspace={workspace}
        onCollapse={() => setSidebarCollapsed((value) => !value)}
        onView={setView}
        onSearch={setSearch}
        onNew={newThread}
        onOpen={openThread}
        onWorkspace={switchWorkspace}
        onRename={renameThread}
        onArchive={archiveThread}
        onFork={forkThread}
        onDelete={deleteThread}
        onSettings={openSettings}
      />

      <div className="content-frame">
        <main className="main-column">
          <Header
            view={view}
            thread={current}
            workspace={workspace}
            workbarOpen={workbarOpen}
            onWorkbar={() => setWorkbarOpen((value) => !value)}
            onNew={newThread}
          />
          {view === "chat" ? (
            <ChatSurface
              items={items}
              busy={busy}
              mode={mode}
              input={input}
              error={error}
              approvals={approvals}
              models={models}
              activeModel={activeModel}
              workspace={workspace}
              runningTask={runningTask}
              listRef={listRef}
              onInput={setInput}
              onMode={setMode}
              onSend={send}
              onModel={switchModel}
              onWorkspace={switchWorkspace}
              onCloseError={() => setError("")}
              onStop={async () => {
                if (runningTask) await api.stopTask(runningTask.id);
              }}
              onApprove={async (approval, approved, scope = "once") => {
                await api.approve(approval.id, approved, scope);
                setApprovals((values) => values.filter((value) => value.id !== approval.id));
              }}
            />
          ) : (
            <ModuleView
              view={view}
              tasks={tasks}
              artifacts={artifacts}
              memory={memory}
              usage={usage}
              threadId={current.id}
              onMemoryChanged={() => refreshThreadData(current.id)}
              showToast={showToast}
            />
          )}
        </main>

        {workbarOpen && (
          <Workbar
            tab={workbarTab}
            tasks={tasks}
            artifacts={artifacts}
            items={items}
            usage={usage}
            workspace={workspace}
            onTab={setWorkbarTab}
            onClose={() => setWorkbarOpen(false)}
          />
        )}
      </div>

      {settingsOpen && settings && (
        <SettingsSurface
          settings={settings}
          models={models}
          activeModel={activeModel}
          theme={theme}
          workspace={workspace}
          threadId={current.id}
          onTheme={setTheme}
          onModel={switchModel}
          onModelsChanged={refreshModels}
          onSettings={setSettings}
          onWorkspace={switchWorkspace}
          onMemoryChanged={() => refreshThreadData(current.id)}
          showToast={showToast}
          onClose={() => setSettingsOpen(false)}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function Sidebar(props: {
  collapsed: boolean;
  view: View;
  threads: ThreadSummary[];
  archivedThreads: ThreadSummary[];
  currentId: string;
  search: string;
  workspace: WorkspaceInfo;
  onCollapse: () => void;
  onView: (view: View) => void;
  onSearch: (value: string) => void;
  onNew: () => void;
  onOpen: (id: string) => void;
  onWorkspace: () => void;
  onRename: (thread: ThreadSummary) => void;
  onArchive: (id: string, archived: boolean) => void;
  onFork: (id: string) => void;
  onDelete: (id: string) => void;
  onSettings: () => void;
}) {
  const [archiveOpen, setArchiveOpen] = useState(false);
  const nav: Array<{ key: View; label: string; icon: typeof MessageSquare }> = [
    { key: "chat", label: "会话", icon: MessageSquare },
    { key: "tasks", label: "任务", icon: ListTodo },
    { key: "artifacts", label: "产物", icon: Box },
    { key: "memory", label: "记忆", icon: Brain },
  ];
  return (
    <aside className="sidebar">
      <div className="sidebar-chrome">
        <div className="brand-mark" title="GraphCoder"><Sparkles size={17} /></div>
        {!props.collapsed && <strong className="brand-name">GraphCoder</strong>}
        <IconButton
          className="collapse-button"
          label={props.collapsed ? "展开侧栏" : "收起侧栏"}
          onClick={props.onCollapse}
        >
          {props.collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
        </IconButton>
      </div>

      <button className="new-session-button" onClick={props.onNew} title="新任务">
        <Plus size={17} />
        {!props.collapsed && <span>新任务</span>}
      </button>

      {!props.collapsed && (
        <label className="search-field">
          <Search size={15} />
          <input
            value={props.search}
            onChange={(event) => props.onSearch(event.target.value)}
            placeholder="搜索会话"
          />
        </label>
      )}

      <nav className="primary-nav" aria-label="主导航">
        {nav.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              className={props.view === item.key ? "active" : ""}
              title={item.label}
              onClick={() => props.onView(item.key)}
            >
              <Icon size={17} />
              {!props.collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {!props.collapsed && (
        <>
          <button className="workspace-row" onClick={props.onWorkspace}>
            <FolderGit2 size={16} />
            <span className="workspace-copy">
              <strong>{props.workspace.name}</strong>
              <small>{props.workspace.branch || compactPath(props.workspace.path)}</small>
            </span>
            <ChevronDown size={14} />
          </button>
          <div className="section-label"><span>会话</span><span>{props.threads.length}</span></div>
          <div className="session-list">
            {props.threads.map((thread) => (
              <SessionRow
                key={thread.id}
                thread={thread}
                active={props.currentId === thread.id}
                onOpen={props.onOpen}
                onRename={props.onRename}
                onArchive={props.onArchive}
                onFork={props.onFork}
                onDelete={props.onDelete}
              />
            ))}
            {!props.threads.length && <p className="empty-list">还没有会话</p>}
            {!!props.archivedThreads.length && (
              <div className="archive-section">
                <button className="archive-toggle" onClick={() => setArchiveOpen((value) => !value)}>
                  {archiveOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  已归档 <span>{props.archivedThreads.length}</span>
                </button>
                {archiveOpen && props.archivedThreads.map((thread) => (
                  <SessionRow
                    key={thread.id}
                    thread={thread}
                    active={props.currentId === thread.id}
                    onOpen={props.onOpen}
                    onRename={props.onRename}
                    onArchive={props.onArchive}
                    onFork={props.onFork}
                    onDelete={props.onDelete}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      <button className="settings-button" onClick={props.onSettings} title="设置">
        <Settings size={17} />
        {!props.collapsed && <span>设置</span>}
      </button>
    </aside>
  );
}

function SessionRow(props: {
  thread: ThreadSummary;
  active: boolean;
  onOpen: (id: string) => void;
  onRename: (thread: ThreadSummary) => void;
  onArchive: (id: string, archived: boolean) => void;
  onFork: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className={`session-row ${props.active ? "active" : ""}`}>
      <button className="session-main" onClick={() => props.onOpen(props.thread.id)}>
        <span>{props.thread.title || "新会话"}</span>
        <small>{relativeTime(props.thread.updated_at)}</small>
      </button>
      <IconButton label="会话操作" className="session-menu-button" onClick={() => setMenuOpen(!menuOpen)}>
        <MoreHorizontal />
      </IconButton>
      {menuOpen && (
        <div className="context-menu" onMouseLeave={() => setMenuOpen(false)}>
          <button onClick={() => props.onRename(props.thread)}><Code2 />重命名</button>
          <button onClick={() => props.onFork(props.thread.id)}><Split />创建分支</button>
          <button onClick={() => props.onArchive(props.thread.id, !props.thread.archived)}>
            {props.thread.archived ? <ArchiveRestore /> : <Archive />}
            {props.thread.archived ? "取消归档" : "归档"}
          </button>
          <button className="danger" onClick={() => props.onDelete(props.thread.id)}>
            <Trash2 />删除
          </button>
        </div>
      )}
    </div>
  );
}

function Header(props: {
  view: View;
  thread: ThreadDetail;
  workspace: WorkspaceInfo;
  workbarOpen: boolean;
  onWorkbar: () => void;
  onNew: () => void;
}) {
  const titles: Record<View, string> = {
    chat: props.thread.title || "新任务",
    tasks: "任务",
    artifacts: "产物",
    memory: "记忆",
  };
  return (
    <header className="chat-header">
      <div className="header-title">
        <strong>{titles[props.view]}</strong>
        {props.workspace.branch && <span><GitBranch size={13} />{props.workspace.branch}</span>}
      </div>
      <div className="header-actions">
        <IconButton label="新任务" onClick={props.onNew}><Plus /></IconButton>
        <IconButton label={props.workbarOpen ? "关闭工作栏" : "打开工作栏"} onClick={props.onWorkbar}>
          {props.workbarOpen ? <PanelRightClose /> : <PanelRightOpen />}
        </IconButton>
      </div>
    </header>
  );
}

function ChatSurface(props: {
  items: UIItem[];
  busy: boolean;
  mode: "chat" | "build";
  input: string;
  error: string;
  approvals: ApprovalInfo[];
  models: ModelInfo[];
  activeModel: string;
  workspace: WorkspaceInfo;
  runningTask?: TaskInfo;
  listRef: React.RefObject<HTMLDivElement>;
  onInput: (value: string) => void;
  onMode: (mode: "chat" | "build") => void;
  onSend: (value?: string) => void;
  onModel: (id: string) => void;
  onWorkspace: () => void;
  onCloseError: () => void;
  onStop: () => void;
  onApprove: (approval: ApprovalInfo, approved: boolean, scope?: string) => void;
}) {
  return (
    <div className="chat-surface">
      <div className="messages" ref={props.listRef}>
        {!props.items.length && (
          <div className="empty-hero">
            <div className="hero-mark"><Sparkles size={30} /></div>
            <header>
              <h1>今天想做点什么？</h1>
              <p>GraphCoder 会在你的项目中阅读、规划、编码和验证。</p>
            </header>
            <div className="starter-list">
              {STARTERS.map((starter) => (
                <button key={starter} onClick={() => props.onSend(starter)}>
                  <span>{starter}</span><ChevronRight size={15} />
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="conversation-measure">
          {props.items.map((item) => <ItemView key={item.id} item={item} />)}
          {props.busy && (
            <div className="processing-row">
              <span className="spinner" />
              <span>{props.mode === "build" ? "多 Agent 正在协作" : "GraphCoder 正在工作"}</span>
            </div>
          )}
        </div>
      </div>

      {!!props.approvals.length && (
        <ApprovalCard approval={props.approvals[0]} onRespond={props.onApprove} />
      )}
      {props.error && (
        <div className="error-banner">
          <span>{props.error}</span>
          <IconButton label="关闭" onClick={props.onCloseError}><X /></IconButton>
        </div>
      )}
      <Composer {...props} />
    </div>
  );
}

function Composer(props: {
  busy: boolean;
  mode: "chat" | "build";
  input: string;
  models: ModelInfo[];
  activeModel: string;
  workspace: WorkspaceInfo;
  runningTask?: TaskInfo;
  onInput: (value: string) => void;
  onMode: (mode: "chat" | "build") => void;
  onSend: () => void;
  onModel: (id: string) => void;
  onWorkspace: () => void;
  onStop: () => void;
}) {
  return (
    <footer className="composer-region">
      <div className="composer-card">
        <textarea
          rows={3}
          value={props.input}
          disabled={props.busy}
          placeholder={props.mode === "build" ? "描述要构建或修改的功能" : "向 GraphCoder 发送消息"}
          onChange={(event) => props.onInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              props.onSend();
            }
          }}
        />
        <div className="composer-toolbar">
          <div className="composer-left">
            <IconButton label="添加项目或附件" onClick={props.onWorkspace}><Paperclip /></IconButton>
            <label className="quiet-select" title="模型">
              <Bot size={15} />
              <select value={props.activeModel} onChange={(event) => props.onModel(event.target.value)}>
                {props.models.map((model) => (
                  <option key={model.id} value={model.id}>{model.name} · {model.model}</option>
                ))}
              </select>
              <ChevronDown size={13} />
            </label>
            <button className="quiet-chip" onClick={props.onWorkspace} title={props.workspace.path}>
              <Folder size={15} /><span>{props.workspace.name}</span>
            </button>
            {!!props.workspace.branch && (
              <span className="quiet-chip static"><GitBranch size={14} />{props.workspace.branch}</span>
            )}
            <span className="permission-control" title="危险操作会先请求批准">
              <ShieldCheck size={15} />询问
            </span>
          </div>
          <div className="composer-right">
            <div className="mode-control" aria-label="运行模式">
              <button className={props.mode === "chat" ? "active" : ""} onClick={() => props.onMode("chat")}>对话</button>
              <button className={props.mode === "build" ? "active" : ""} onClick={() => props.onMode("build")}>构建</button>
            </div>
            {props.busy ? (
              <IconButton label="停止" className="send-button stop" onClick={props.onStop}><CircleStop /></IconButton>
            ) : (
              <IconButton
                label="发送"
                className="send-button"
                disabled={!props.input.trim()}
                onClick={props.onSend}
              >
                <Send />
              </IconButton>
            )}
          </div>
        </div>
      </div>
      <span className="composer-note">GraphCoder 可能会出错，请检查重要改动。</span>
    </footer>
  );
}

function ItemView({ item }: { item: UIItem }) {
  if (item.kind === "user_message") {
    return <div className="turn user-turn"><Markdown text={item.content || ""} /></div>;
  }
  if (item.kind === "tool_call") return <ToolCard item={item} />;
  return (
    <article className="turn assistant-turn">
      <div className="assistant-label"><Sparkles size={14} />{roleName(item.role)}</div>
      {item.content ? <Markdown text={item.content} /> : <span className="muted">正在思考...</span>}
    </article>
  );
}

function ToolCard({ item }: { item: UIItem }) {
  const [open, setOpen] = useState(false);
  const status = item.blocked ? "已阻止" : item.running ? "运行中" : "完成";
  return (
    <div className="tool-card" data-status={item.blocked ? "blocked" : item.running ? "running" : "done"}>
      <button className="tool-card-header" onClick={() => setOpen((value) => !value)}>
        <FileCode2 size={15} />
        <span>{toolName(item.name)}</span>
        <small>{status}</small>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open && (
        <div className="tool-details">
          {!!item.arguments && <pre>{JSON.stringify(item.arguments, null, 2)}</pre>}
          {!!item.result && <pre>{item.result.slice(0, 5000)}</pre>}
        </div>
      )}
    </div>
  );
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
          pre: ({ children }) => <pre className="code-block">{children}</pre>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function ApprovalCard(props: {
  approval: ApprovalInfo;
  onRespond: (approval: ApprovalInfo, approved: boolean, scope?: string) => void;
}) {
  return (
    <div className="approval-card">
      <div><ShieldCheck size={18} /><strong>需要你的批准</strong></div>
      <code>{props.approval.target}</code>
      <p>{props.approval.reason}</p>
      <div className="approval-actions">
        <button onClick={() => props.onRespond(props.approval, false)}>拒绝</button>
        <button onClick={() => props.onRespond(props.approval, true, "always")}>始终允许</button>
        <button className="primary" onClick={() => props.onRespond(props.approval, true)}>允许</button>
      </div>
    </div>
  );
}

function Workbar(props: {
  tab: WorkbarTab;
  tasks: TaskInfo[];
  artifacts: ArtifactInfo[];
  items: UIItem[];
  usage: { total_tokens: number; calls: number; cost: number };
  workspace: WorkspaceInfo;
  onTab: (tab: WorkbarTab) => void;
  onClose: () => void;
}) {
  return (
    <aside className="workbar">
      <div className="workbar-header">
        <div className="workbar-tabs">
          <button className={props.tab === "tasks" ? "active" : ""} onClick={() => props.onTab("tasks")}>任务</button>
          <button className={props.tab === "files" ? "active" : ""} onClick={() => props.onTab("files")}>文件</button>
          <button className={props.tab === "activity" ? "active" : ""} onClick={() => props.onTab("activity")}>活动</button>
        </div>
        <IconButton label="关闭工作栏" onClick={props.onClose}><X /></IconButton>
      </div>
      {props.tab === "tasks" && <TaskPanel tasks={props.tasks} usage={props.usage} />}
      {props.tab === "files" && <FileBrowser workspace={props.workspace} artifacts={props.artifacts} />}
      {props.tab === "activity" && <ActivityPanel items={props.items} />}
    </aside>
  );
}

function TaskPanel(props: {
  tasks: TaskInfo[];
  usage: { total_tokens: number; calls: number; cost: number };
}) {
  return (
    <div className="workbar-body">
      <div className="metrics-row">
        <span><strong>{props.tasks.length}</strong>任务</span>
        <span><strong>{formatNumber(props.usage.total_tokens)}</strong>Tokens</span>
        <span><strong>{props.usage.calls}</strong>调用</span>
      </div>
      <div className="panel-section-title"><span>任务记录</span></div>
      <div className="ledger-list">
        {props.tasks.map((task) => (
          <div className="ledger-row" key={task.id}>
            <span className={`status-dot ${task.status}`} />
            <div><strong>{task.mode === "build" ? "构建" : "对话"}</strong><p>{task.content}</p></div>
            <small>{statusName(task.status)}</small>
          </div>
        ))}
        {!props.tasks.length && <EmptyPanel icon={<ListTodo />} text="任务会显示在这里" />}
      </div>
    </div>
  );
}

function FileBrowser(props: { workspace: WorkspaceInfo; artifacts: ArtifactInfo[] }) {
  const [path, setPath] = useState(".");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [preview, setPreview] = useState<{ path: string; content: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (nextPath: string) => {
    setLoading(true);
    try {
      const data = await api.listFiles(nextPath);
      setPath(nextPath);
      setEntries(data.entries);
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load("."); }, [load, props.workspace.path]);

  const inspect = async (entry: FileEntry) => {
    if (entry.kind === "directory") {
      await load(entry.path);
      return;
    }
    try {
      const result = await api.artifactPreview(entry.path);
      setPreview({ path: entry.path, content: result.content });
    } catch {
      await openPath(entry.path);
    }
  };

  if (preview) {
    return (
      <div className="workbar-body file-preview">
        <div className="file-preview-header">
          <button onClick={() => setPreview(null)}><ChevronRight className="back-icon" />返回</button>
          <div>
            <IconButton label="在系统中打开" onClick={() => openPath(preview.path)}><ExternalLink /></IconButton>
            <IconButton label="在 Finder 中显示" onClick={() => revealPath(preview.path)}><Folder /></IconButton>
          </div>
        </div>
        <strong>{preview.path.split("/").pop()}</strong>
        <pre>{preview.content}</pre>
      </div>
    );
  }

  return (
    <div className="workbar-body">
      <div className="file-breadcrumb">
        <button onClick={() => load(".")}><FolderGit2 size={15} />{props.workspace.name}</button>
        {path !== "." && <button onClick={() => load(parentPath(path))}>/ {path}</button>}
      </div>
      <div className="file-list" data-loading={loading || undefined}>
        {entries.map((entry) => (
          <button key={entry.path} onClick={() => inspect(entry)}>
            {entry.kind === "directory" ? <Folder size={16} /> : <File size={16} />}
            <span>{entry.name}</span>
            {entry.kind === "file" && <small>{formatSize(entry.size)}</small>}
            <ChevronRight size={13} />
          </button>
        ))}
        {!entries.length && !loading && <EmptyPanel icon={<Folder />} text="这个目录是空的" />}
      </div>
      {!!props.artifacts.length && (
        <>
          <div className="panel-section-title"><span>本次产物</span><span>{props.artifacts.length}</span></div>
          <div className="artifact-chips">
            {props.artifacts.map((artifact) => (
              <button key={artifact.id} onClick={() => revealPath(artifact.path)}>{artifact.path}</button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ActivityPanel({ items }: { items: UIItem[] }) {
  const tools = items.filter((item) => item.kind === "tool_call");
  return (
    <div className="workbar-body activity-list">
      {tools.map((item) => (
        <div key={item.id}>
          <span className={`status-dot ${item.running ? "running" : item.blocked ? "error" : "completed"}`} />
          <FileCode2 size={15} />
          <div><strong>{toolName(item.name)}</strong><small>{item.running ? "运行中" : item.blocked ? "已阻止" : "完成"}</small></div>
        </div>
      ))}
      {!tools.length && <EmptyPanel icon={<History />} text="工具活动会显示在这里" />}
    </div>
  );
}

function ModuleView(props: {
  view: Exclude<View, "chat">;
  tasks: TaskInfo[];
  artifacts: ArtifactInfo[];
  memory: MemoryEntry[];
  usage: { total_tokens: number; calls: number; cost: number };
  threadId: string;
  onMemoryChanged: () => void;
  showToast: (message: string) => void;
}) {
  if (props.view === "tasks") {
    return (
      <div className="module-page">
        <PageHeading title="任务" description="当前会话的运行记录、状态和用量" />
        <TaskPanel tasks={props.tasks} usage={props.usage} />
      </div>
    );
  }
  if (props.view === "artifacts") {
    return (
      <div className="module-page">
        <PageHeading title="产物" description="GraphCoder 在当前项目中创建或修改的文件" />
        <div className="artifact-table">
          {props.artifacts.map((artifact) => (
            <button key={artifact.id} onClick={() => revealPath(artifact.path)}>
              <FileCode2 /><span>{artifact.path}</span><small>{formatSize(artifact.size)}</small><ExternalLink />
            </button>
          ))}
          {!props.artifacts.length && <EmptyPanel icon={<Box />} text="当前会话还没有产物" />}
        </div>
      </div>
    );
  }
  return (
    <MemoryManager
      entries={props.memory}
      threadId={props.threadId}
      onChanged={props.onMemoryChanged}
      showToast={props.showToast}
      standalone
    />
  );
}

interface NotificationContext {
  setItems: React.Dispatch<React.SetStateAction<UIItem[]>>;
  itemRef: React.MutableRefObject<Record<string, UIItem>>;
  streamRef: React.MutableRefObject<Record<string, string>>;
  setBusy: (busy: boolean) => void;
  setApprovals: React.Dispatch<React.SetStateAction<ApprovalInfo[]>>;
  setError: (error: string) => void;
  onSettled: () => void;
}

export function handleNotification(method: string, params: Record<string, unknown>, context: NotificationContext) {
  const id = String(params.item_id || "");
  const kind = String(params.kind || "");
  if (method === "item/started" && kind !== "user_message") {
    const item: UIItem = kind === "tool_call"
      ? { id, kind: "tool_call", name: String(params.name || "tool"), arguments: (params.arguments as Record<string, unknown>) || {}, running: true }
      : { id, kind: "agent_message", role: String(params.role || "assistant"), content: "", running: true };
    // One backend item id must map to exactly one UI entry; the engine reuses
    // the same agent item across tool rounds, so never split or duplicate it.
    context.itemRef.current[id] = item;
    if (kind === "agent_message") {
      // Defer the bubble until the first delta so entries stay in time order
      // (tool calls that happen before any text render above the message).
      context.streamRef.current[id] = "";
    } else {
      context.setItems((previous) => previous.some((value) => value.id === id) ? previous : [...previous, item]);
    }
  } else if (method === "item/delta") {
    const delta = String(params.delta || "");
    const streamId = id || Object.keys(context.streamRef.current).pop() || "";
    const item = context.itemRef.current[streamId];
    if (item) {
      item.content = (item.content || "") + delta;
      context.streamRef.current[streamId] = item.content;
      context.setItems((previous) => previous.some((value) => value.id === streamId)
        ? previous.map((value) => (value.id === streamId ? { ...item } : value))
        : [...previous, { ...item }]);
    }
  } else if (method === "item/completed") {
    const payload = (params.payload as Record<string, unknown>) || {};
    const item = context.itemRef.current[id];
    if (kind === "agent_message") {
      const completed = { ...(item || { id, kind: "agent_message" as const }), content: String(payload.content ?? context.streamRef.current[id] ?? ""), running: false };
      context.itemRef.current[id] = completed;
      context.setItems((previous) => previous.some((value) => value.id === id) ? previous.map((value) => value.id === id ? completed : value) : [...previous, completed]);
    } else if (kind === "tool_call" && item) {
      const completed = { ...item, running: false, blocked: Boolean(payload.blocked), result: payload.result ? String(payload.result) : undefined };
      context.itemRef.current[id] = completed;
      context.setItems((previous) => previous.map((value) => value.id === id ? completed : value));
    }
  } else if (method === "approval/requested") {
    context.setApprovals((previous) => [...previous.filter((value) => value.id !== String(params.id)), { id: String(params.id), kind: String(params.kind || "tool"), target: String(params.target || ""), reason: String(params.reason || "") }]);
  } else if (method === "turn/started") {
    context.setBusy(true);
  } else if (method === "turn/completed") {
    context.setBusy(false);
    context.onSettled();
  } else if (method === "error") {
    context.setError(String(params.message || "任务执行出错"));
    context.setBusy(false);
  }
}

export function rebuildItems(events: RuntimeEvent[]): UIItem[] {
  const output: UIItem[] = [];
  const placed: Record<string, UIItem> = {};
  const pending: Record<string, UIItem> = {};
  for (const event of events) {
    const params = event.payload;
    const payload = (params.payload as Record<string, unknown>) || {};
    const kind = String(params.kind || "");
    const id = String(event.item_id || event.seq);
    if (event.type === "item/started" && kind === "tool_call") {
      const item: UIItem = { id, kind: "tool_call", name: String(params.name || "tool"), arguments: (params.arguments as Record<string, unknown>) || {} };
      placed[id] = item;
      output.push(item);
    } else if (event.type === "item/started" && kind === "agent_message") {
      // Hold the bubble until its first delta so ordering matches the live view.
      pending[id] = { id, kind: "agent_message", role: String(params.role || "assistant"), content: "" };
    } else if (event.type === "item/delta" && pending[id]) {
      placed[id] = pending[id];
      delete pending[id];
      output.push(placed[id]);
    } else if (event.type === "item/completed" && kind === "user_message") {
      output.push({ id, kind: "user_message", content: String(payload.content || "") });
    } else if (event.type === "item/completed" && kind === "agent_message") {
      const item = placed[id] || pending[id];
      if (!item) {
        output.push({ id, kind: "agent_message", content: String(payload.content || "") });
      } else {
        item.content = String(payload.content || "");
        if (pending[id]) {
          delete pending[id];
          placed[id] = item;
          output.push(item);
        }
      }
    } else if (event.type === "item/completed" && kind === "tool_call" && placed[id]) {
      placed[id].blocked = Boolean(payload.blocked);
      placed[id].result = payload.result ? String(payload.result) : undefined;
    }
  }
  return output;
}

function matches(value: string, query: string) { return value.toLowerCase().includes(query.trim().toLowerCase()); }
function compactPath(path: string) { if (!path) return "未选择项目"; const parts = path.split("/").filter(Boolean); return parts.length > 2 ? `.../${parts.slice(-2).join("/")}` : path; }
function parentPath(path: string) { const parts = path.split("/").filter(Boolean); parts.pop(); return parts.join("/") || "."; }
function relativeTime(timestamp: number) { const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp)); if (seconds < 60) return "刚刚"; if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`; if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时`; return `${Math.floor(seconds / 86400)} 天`; }
function formatSize(bytes: number) { if (bytes < 1024) return `${bytes} B`; if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`; return `${(bytes / 1048576).toFixed(1)} MB`; }
function formatNumber(value: number) { return new Intl.NumberFormat("zh-CN", { notation: value > 9999 ? "compact" : "standard" }).format(value); }
function errorMessage(reason: unknown, fallback: string) { return reason instanceof Error ? reason.message : fallback; }
function roleName(role?: string) { const names: Record<string, string> = { pm: "产品经理", architect: "架构师", developer: "开发者", reviewer: "代码审查", qa: "质量验证", assistant: "GraphCoder" }; return names[role || "assistant"] || role || "GraphCoder"; }
function toolName(name?: string) { const names: Record<string, string> = { read_file: "读取文件", write_file: "写入文件", apply_patch: "应用修改", list_files: "浏览文件", search_files: "搜索代码", shell: "运行命令", web_search: "搜索网络" }; return names[name || ""] || name || "工具调用"; }
function statusName(status: string) { const names: Record<string, string> = { pending: "等待中", running: "运行中", completed: "已完成", error: "失败", cancelled: "已停止" }; return names[status] || status; }
