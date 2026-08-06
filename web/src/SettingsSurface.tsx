/* Full-screen settings center modeled after maka-agent's settings surface. */

import { useCallback, useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowLeft,
  BarChart3,
  Bot,
  Brain,
  CalendarDays,
  Check,
  Database,
  FolderOpen,
  Globe,
  HeartPulse,
  Info,
  KeyRound,
  Loader2,
  Monitor,
  Moon,
  Palette,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Terminal,
} from "lucide-react";
import { api, openPath, revealPath } from "./api";
import type {
  DailyUsage,
  DataSummary,
  HealthSummary,
  MemoryEntry,
  ModelInfo,
  ModelUsage,
  ProviderTestResult,
  SettingsInfo,
  WorkspaceInfo,
} from "./api";
import { ModelsPage } from "./SettingsModels";
import { MemoryManager, PageHeading, PermissionManager, SettingsSection } from "./widgets";

export type Theme = "light" | "dark" | "system";

type PageId =
  | "general"
  | "appearance"
  | "models"
  | "usage"
  | "memory"
  | "review"
  | "websearch"
  | "data"
  | "permissions"
  | "health"
  | "about";

interface NavItem {
  key: PageId;
  label: string;
  icon: LucideIcon;
  beta?: boolean;
}

const GROUPS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "通用",
    items: [
      { key: "general", label: "通用", icon: Settings },
      { key: "appearance", label: "外观", icon: Palette },
    ],
  },
  {
    label: "AI 与集成",
    items: [
      { key: "models", label: "模型", icon: Bot },
      { key: "usage", label: "使用统计", icon: BarChart3 },
      { key: "memory", label: "记忆", icon: Brain },
      { key: "review", label: "每日回顾", icon: CalendarDays },
      { key: "websearch", label: "联网搜索", icon: Globe, beta: true },
    ],
  },
  {
    label: "系统",
    items: [
      { key: "data", label: "数据", icon: Database },
      { key: "permissions", label: "权限与能力", icon: ShieldCheck },
      { key: "health", label: "健康", icon: HeartPulse },
      { key: "about", label: "关于", icon: Info },
    ],
  },
];

export interface SettingsSurfaceProps {
  settings: SettingsInfo;
  models: ModelInfo[];
  activeModel: string;
  theme: Theme;
  workspace: WorkspaceInfo;
  threadId: string;
  onTheme: (theme: Theme) => void;
  onModel: (id: string) => void;
  onModelsChanged: () => Promise<void>;
  onSettings: (settings: SettingsInfo) => void;
  onWorkspace: () => void;
  onMemoryChanged: () => void;
  showToast: (message: string) => void;
  onClose: () => void;
}

export default function SettingsSurface(props: SettingsSurfaceProps) {
  const [page, setPage] = useState<PageId>("general");

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") props.onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [props.onClose]);

  return (
    <div className="settings-surface" role="dialog" aria-modal="true" aria-label="设置">
      <aside className="settings-nav">
        <button className="back-to-app" onClick={props.onClose}>
          <ArrowLeft size={15} />
          <span>返回应用</span>
        </button>
        {GROUPS.map((group) => (
          <div className="nav-group" key={group.label}>
            <span className="nav-group-label">{group.label}</span>
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.key}
                  className={page === item.key ? "active" : ""}
                  onClick={() => setPage(item.key)}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                  {item.beta && <span className="beta-pill">Beta</span>}
                </button>
              );
            })}
          </div>
        ))}
      </aside>
      <section className="settings-page-wrap">
        {page === "general" && <GeneralPage {...props} />}
        {page === "appearance" && <AppearancePage {...props} />}
        {page === "models" && (
          <ModelsPage
            models={props.models}
            activeModel={props.activeModel}
            onModel={props.onModel}
            onChanged={props.onModelsChanged}
            showToast={props.showToast}
          />
        )}
        {page === "usage" && <UsagePage />}
        {page === "memory" && <MemoryPage {...props} />}
        {page === "review" && <DailyReviewPage />}
        {page === "websearch" && <WebSearchPage {...props} />}
        {page === "data" && <DataPage />}
        {page === "permissions" && <PermissionsPage {...props} />}
        {page === "health" && <HealthPage />}
        {page === "about" && <AboutPage />}
      </section>
    </div>
  );
}

function GeneralPage(props: SettingsSurfaceProps) {
  const mode = props.settings.options.default_mode === "build" ? "build" : "chat";
  const setMode = async (value: "chat" | "build") => {
    await api.setOption({ default_mode: value });
    props.onSettings(await api.getSettings());
    props.showToast(value === "build" ? "默认模式已设为构建" : "默认模式已设为对话");
  };
  return (
    <div className="settings-page-inner">
      <PageHeading title="通用" description="工作区与默认行为。" />
      <SettingsSection title="工作区" description="GraphCoder 当前正在处理的项目目录">
        <div className="setting-row">
          <FolderOpen size={17} />
          <span className="grow">
            <strong>{props.workspace.name || "未选择项目"}</strong>
            <small>
              {props.workspace.path}
              {props.workspace.is_git ? ` · ${props.workspace.branch}` : ""}
            </small>
          </span>
          <button className="quiet-button" onClick={props.onWorkspace}>切换</button>
        </div>
      </SettingsSection>
      <SettingsSection title="默认会话模式" description="新会话的初始模式，随时可在输入框中切换">
        <div className="mode-segment" role="radiogroup" aria-label="默认会话模式">
          <button className={mode === "chat" ? "active" : ""} onClick={() => void setMode("chat")}>对话</button>
          <button className={mode === "build" ? "active" : ""} onClick={() => void setMode("build")}>构建</button>
        </div>
      </SettingsSection>
    </div>
  );
}

function AppearancePage(props: SettingsSurfaceProps) {
  const options: Array<{ key: Theme; label: string; icon: LucideIcon }> = [
    { key: "light", label: "浅色", icon: Sun },
    { key: "dark", label: "深色", icon: Moon },
    { key: "system", label: "跟随系统", icon: Monitor },
  ];
  return (
    <div className="settings-page-inner">
      <PageHeading title="外观" description="选择 GraphCoder 的显示方式" />
      <SettingsSection title="主题" description="跟随系统会随操作系统外观自动切换">
        <div className="theme-options three">
          {options.map((option) => {
            const Icon = option.icon;
            return (
              <button
                key={option.key}
                className={props.theme === option.key ? "active" : ""}
                onClick={() => props.onTheme(option.key)}
              >
                <Icon />
                {option.label}
                <Check />
              </button>
            );
          })}
        </div>
      </SettingsSection>
    </div>
  );
}

function UsagePage() {
  const [stats, setStats] = useState<{ total_tokens: number; calls: number; cost: number } | null>(null);
  const [daily, setDaily] = useState<DailyUsage[]>([]);
  const [byModel, setByModel] = useState<ModelUsage[]>([]);

  useEffect(() => {
    let alive = true;
    Promise.all([api.usageStats(), api.usageDaily(14)])
      .then(([summary, detail]) => {
        if (!alive) return;
        setStats(summary);
        setDaily(detail.daily);
        setByModel(detail.by_model);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const peak = Math.max(1, ...daily.map((day) => day.input_tokens + day.output_tokens));

  return (
    <div className="settings-page-inner">
      <PageHeading title="使用统计" description="本地记录的模型调用与 token 用量" />
      <SettingsSection title="总览" description="自开始使用以来的累计数据">
        <div className="usage-grid">
          <div><strong>{stats ? formatNumber(stats.total_tokens) : "…"}</strong><span>Tokens</span></div>
          <div><strong>{stats ? formatNumber(stats.calls) : "…"}</strong><span>模型调用</span></div>
          <div><strong>{stats ? `$${stats.cost.toFixed(4)}` : "…"}</strong><span>估算成本</span></div>
        </div>
      </SettingsSection>
      <SettingsSection title="最近 14 天" description="每日输入 + 输出 token 总量">
        <div className="usage-chart" aria-label="最近 14 天用量柱状图">
          {daily.map((day) => {
            const total = day.input_tokens + day.output_tokens;
            return (
              <div
                className="usage-bar-col"
                key={day.day}
                title={`${day.day}：${formatNumber(total)} tokens · ${day.calls} 次调用`}
              >
                <div className="usage-bar" style={{ height: `${Math.max(2, Math.round((total / peak) * 100))}%` }} />
                <small>{day.day.slice(8)}</small>
              </div>
            );
          })}
          {!daily.length && <p className="catalog-empty">暂无用量记录</p>}
        </div>
      </SettingsSection>
      <SettingsSection title="按模型" description="token 用量最高的模型">
        <div className="model-usage-list">
          {byModel.map((row) => (
            <div className="model-usage-row" key={`${row.provider}-${row.model}`}>
              <span className="grow"><strong>{row.model}</strong><small>{row.provider}</small></span>
              <span className="metric">{formatNumber(row.tokens)} tokens</span>
              <span className="metric">{row.calls} 次</span>
              <span className="metric">${row.cost.toFixed(4)}</span>
            </div>
          ))}
          {!byModel.length && <p className="catalog-empty">暂无模型用量</p>}
        </div>
      </SettingsSection>
    </div>
  );
}

function DailyReviewPage() {
  const [data, setData] = useState<{ daily: DailyUsage[]; today_tasks: number } | null>(null);

  useEffect(() => {
    let alive = true;
    api.usageDaily(7).then((detail) => {
      if (alive) setData(detail);
    }).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const today = data?.daily.length ? data.daily[data.daily.length - 1] : undefined;

  return (
    <div className="settings-page-inner">
      <PageHeading title="每日回顾" description="最近一周的活动与用量回顾" />
      <SettingsSection title="今天" description="今日任务与 token 消耗">
        <div className="usage-grid">
          <div><strong>{data ? formatNumber(data.today_tasks) : "…"}</strong><span>今日任务</span></div>
          <div><strong>{today ? formatNumber(today.input_tokens + today.output_tokens) : "0"}</strong><span>Tokens</span></div>
          <div><strong>{today ? formatNumber(today.calls) : "0"}</strong><span>模型调用</span></div>
        </div>
      </SettingsSection>
      <SettingsSection title="最近 7 天" description="按天查看调用与成本">
        <div className="model-usage-list">
          {(data?.daily || []).slice().reverse().map((day) => (
            <div className="model-usage-row" key={day.day}>
              <span className="grow"><strong>{day.day}</strong></span>
              <span className="metric">{formatNumber(day.input_tokens + day.output_tokens)} tokens</span>
              <span className="metric">{day.calls} 次</span>
              <span className="metric">${day.cost.toFixed(4)}</span>
            </div>
          ))}
          {!data?.daily.length && <p className="catalog-empty">暂无记录</p>}
        </div>
      </SettingsSection>
    </div>
  );
}

function WebSearchPage(props: SettingsSurfaceProps) {
  const enabled = props.settings.options.enable_web !== false;
  const toggle = async (next: boolean) => {
    await api.setOption({ enable_web: next });
    props.onSettings(await api.getSettings());
    props.showToast(next ? "联网搜索已开启" : "联网搜索已关闭");
  };
  return (
    <div className="settings-page-inner">
      <PageHeading title="联网搜索" description="允许 Agent 在任务中检索网络信息（Beta）" />
      <SettingsSection title="联网搜索" description="关闭后 Agent 不再调用 web_search 工具，立即生效">
        <div className="setting-row">
          <Globe size={17} />
          <span className="grow">
            <strong>联网搜索</strong>
            <small>为 Agent 提供实时网络检索能力</small>
          </span>
          <Switch checked={enabled} label="联网搜索" onChange={(next) => void toggle(next)} />
        </div>
      </SettingsSection>
    </div>
  );
}

function PermissionsPage(props: SettingsSurfaceProps) {
  const shellEnabled = props.settings.options.enable_shell !== false;
  const toggle = async (next: boolean) => {
    await api.setOption({ enable_shell: next });
    props.onSettings(await api.getSettings());
    props.showToast(next ? "命令执行已开启" : "命令执行已关闭");
  };
  return (
    <div className="settings-page-inner">
      <PageHeading title="权限与能力" description="控制工具执行前的审批方式与可用能力" />
      <SettingsSection title="能力" description="关闭后 Agent 将不再调用对应工具，立即生效">
        <div className="setting-row">
          <Terminal size={17} />
          <span className="grow">
            <strong>命令执行</strong>
            <small>允许 Agent 在项目内运行 shell 命令</small>
          </span>
          <Switch checked={shellEnabled} label="命令执行" onChange={(next) => void toggle(next)} />
        </div>
      </SettingsSection>
      <PermissionManager settings={props.settings} onSettings={props.onSettings} />
    </div>
  );
}

function DataPage() {
  const [data, setData] = useState<DataSummary | null>(null);

  useEffect(() => {
    let alive = true;
    api.dataSummary().then((summary) => {
      if (alive) setData(summary);
    }).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const counts = data?.counts || {};

  return (
    <div className="settings-page-inner">
      <PageHeading title="数据" description="GraphCoder 在本机保存的全部数据" />
      <SettingsSection title="存储" description="数据库与配置文件位置">
        <div className="settings-stack">
          <div className="setting-row">
            <Database size={17} />
            <span className="grow"><strong>会话数据库</strong><small>{data?.db_path || "…"}</small></span>
            <span className="metric">{data ? formatSize(data.db_size) : ""}</span>
            <button className="quiet-button" onClick={() => data && void revealPath(data.db_path)}>显示</button>
          </div>
          <div className="setting-row">
            <Settings size={17} />
            <span className="grow"><strong>设置文件</strong><small>{data?.settings_path || "…"}</small></span>
            <span className="metric">{data ? formatSize(data.settings_size) : ""}</span>
          </div>
          <div className="setting-row">
            <FolderOpen size={17} />
            <span className="grow"><strong>数据目录</strong><small>{data?.home || "…"}</small></span>
            <button className="quiet-button" onClick={() => data && void openPath(data.home)}>打开</button>
          </div>
        </div>
      </SettingsSection>
      <SettingsSection title="记录数量" description="各数据表的本地记录条数">
        <div className="usage-grid">
          <div><strong>{formatNumber(counts.sessions ?? 0)}</strong><span>会话</span></div>
          <div><strong>{formatNumber(counts.tasks ?? 0)}</strong><span>任务</span></div>
          <div><strong>{formatNumber(counts.runtime_events ?? 0)}</strong><span>事件</span></div>
          <div><strong>{formatNumber(counts.memory ?? 0)}</strong><span>记忆</span></div>
          <div><strong>{formatNumber(counts.artifacts ?? 0)}</strong><span>产物</span></div>
        </div>
      </SettingsSection>
    </div>
  );
}

function HealthPage() {
  const [health, setHealth] = useState<HealthSummary | null>(null);
  const [probing, setProbing] = useState(false);
  const [probe, setProbe] = useState<ProviderTestResult | null>(null);

  useEffect(() => {
    let alive = true;
    api.healthSummary().then((summary) => {
      if (alive) setHealth(summary);
    }).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const runProbe = async () => {
    if (!health) return;
    setProbing(true);
    setProbe(null);
    try {
      setProbe(await api.testProvider({ id: health.active_provider.id }));
    } catch (reason) {
      setProbe({
        ok: false,
        latency_ms: 0,
        detail: "",
        error: reason instanceof Error ? reason.message : String(reason),
      });
    } finally {
      setProbing(false);
    }
  };

  return (
    <div className="settings-page-inner">
      <PageHeading title="健康" description="运行时状态与连接诊断" />
      <SettingsSection title="运行时" description="当前 GraphCoder Runtime 的基本信息">
        <div className="settings-stack">
          <div className="setting-row">
            <HeartPulse size={17} />
            <span className="grow"><strong>版本</strong><small>GraphCoder {health?.version || "…"} · 协议 {health?.protocol || "…"}</small></span>
          </div>
          <div className="setting-row">
            <Terminal size={17} />
            <span className="grow"><strong>Python</strong><small>{health?.python || "…"}</small></span>
            <span className="metric">{health?.system || ""}</span>
          </div>
          <div className="setting-row">
            <Monitor size={17} />
            <span className="grow"><strong>运行时间</strong><small>自本次启动以来</small></span>
            <span className="metric">{health ? formatUptime(health.uptime_s) : "…"}</span>
          </div>
          <div className="setting-row">
            <FolderOpen size={17} />
            <span className="grow"><strong>工作区</strong><small>{health?.workspace || "…"}</small></span>
          </div>
        </div>
      </SettingsSection>
      <SettingsSection title="连接诊断" description="对当前默认模型发起一次最小调用">
        <div className="setting-row">
          <Bot size={17} />
          <span className="grow">
            <strong>{health?.active_provider.name || "…"}</strong>
            <small>{health?.active_provider.model || ""}</small>
          </span>
          <button className="quiet-button" disabled={probing || !health} onClick={() => void runProbe()}>
            {probing ? <Loader2 size={15} className="spin" /> : <KeyRound size={15} />}
            探测连接
          </button>
        </div>
        {probe && (
          <p className={probe.ok ? "test-ok" : "test-fail"}>
            {probe.ok
              ? `连接成功（${probe.latency_ms}ms）${probe.detail ? `：${probe.detail}` : ""}`
              : `连接失败：${probe.error}`}
          </p>
        )}
      </SettingsSection>
    </div>
  );
}

function AboutPage() {
  const [health, setHealth] = useState<HealthSummary | null>(null);

  useEffect(() => {
    let alive = true;
    api.healthSummary().then((summary) => {
      if (alive) setHealth(summary);
    }).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="settings-page-inner">
      <PageHeading title="关于" description="版本与致谢" />
      <SettingsSection title="GraphCoder Desktop" description="多 Agent 编程工作台">
        <div className="about-mark">
          <Sparkles />
          <strong>GraphCoder</strong>
          <span>Version {health?.version || "…"}</span>
        </div>
        <p className="settings-paragraph">
          设置中心的界面与交互参考 Maka Agent；GraphCoder Runtime、数据与工具执行链由本项目提供。
        </p>
        <p className="settings-paragraph">
          协议 {health?.protocol || "…"} · Python {health?.python || "…"} · {health?.system || ""}
        </p>
      </SettingsSection>
    </div>
  );
}

function MemoryPage(props: SettingsSurfaceProps) {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);

  const load = useCallback(async () => {
    try {
      setEntries((await api.memoryList(props.threadId)).memory);
    } catch {
      /* keep previous entries on refresh failure */
    }
  }, [props.threadId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="settings-page-inner">
      <PageHeading title="记忆" description="让 GraphCoder 在后续回合中保留重要上下文" />
      <MemoryManager
        entries={entries}
        threadId={props.threadId}
        onChanged={() => {
          void load();
          props.onMemoryChanged();
        }}
        showToast={props.showToast}
      />
    </div>
  );
}

function Switch(props: { checked: boolean; label: string; onChange: (next: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={props.checked}
      aria-label={props.label}
      className={`switch ${props.checked ? "on" : ""}`}
      onClick={() => props.onChange(!props.checked)}
    >
      <span />
    </button>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN", { notation: value > 9999 ? "compact" : "standard" }).format(value);
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function formatUptime(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时`;
  return `${Math.floor(seconds / 86400)} 天`;
}
