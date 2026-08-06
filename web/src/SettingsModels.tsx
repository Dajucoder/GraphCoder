/* Models settings page: connected list, provider catalog, connect/edit flows. */

import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ChevronRight,
  KeyRound,
  Loader2,
  RefreshCw,
  Save,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { api } from "./api";
import type { ModelInfo, ProviderInput, ProviderTestResult } from "./api";
import { EmptyPanel, IconButton, SettingsSection } from "./widgets";

type Category = "api" | "aggregator" | "local" | "account" | "plan";

interface CatalogEntry {
  id: string;
  name: string;
  desc: string;
  kind: string;
  category: Category;
  badge: string;
  base_url?: string;
  model?: string;
  hue: number;
}

const CATALOG: CatalogEntry[] = [
  { id: "openai", name: "OpenAI", desc: "OpenAI 官方接入", kind: "openai-compatible", category: "api", badge: "API", base_url: "https://api.openai.com/v1", model: "gpt-4o", hue: 152 },
  { id: "anthropic", name: "Anthropic", desc: "Anthropic 官方接入", kind: "anthropic", category: "api", badge: "API", model: "claude-sonnet-4-5", hue: 24 },
  { id: "gemini", name: "Google Gemini", desc: "Google AI Studio 接入", kind: "gemini", category: "api", badge: "API", model: "gemini-2.5-pro", hue: 210 },
  { id: "grok", name: "xAI Grok", desc: "SuperGrok / X Premium 账号 API", kind: "openai-compatible", category: "api", badge: "API", base_url: "https://api.x.ai/v1", model: "grok-4", hue: 0 },
  { id: "deepseek", name: "DeepSeek", desc: "DeepSeek 官方 API", kind: "openai-compatible", category: "api", badge: "API", base_url: "https://api.deepseek.com/v1", model: "deepseek-chat", hue: 222 },
  { id: "moonshot", name: "Moonshot Kimi", desc: "Moonshot 官方 API，支持 Kimi 模型计划", kind: "openai-compatible", category: "api", badge: "API", base_url: "https://api.moonshot.cn/v1", model: "kimi-k2", hue: 265 },
  { id: "zhipu", name: "智谱 GLM", desc: "智谱开放平台 API", kind: "openai-compatible", category: "api", badge: "API", base_url: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-plus", hue: 200 },
  { id: "qwen", name: "通义千问 Qwen", desc: "阿里云 DashScope API", kind: "openai-compatible", category: "api", badge: "API", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-max", hue: 280 },
  { id: "stepfun", name: "阶跃星辰 StepFun", desc: "阶跃星辰开放平台 API", kind: "openai-compatible", category: "api", badge: "API", base_url: "https://api.stepfun.com/v1", model: "step-2-16k", hue: 180 },
  { id: "siliconflow", name: "SiliconFlow", desc: "硅基流动多模型 API，支持精确模型 ID", kind: "openai-compatible", category: "aggregator", badge: "聚合", base_url: "https://api.siliconflow.cn/v1", model: "deepseek-ai/DeepSeek-V3", hue: 320 },
  { id: "custom-openai", name: "自定义中转站（OpenAI Chat）", desc: "连接任意 OpenAI 兼容中转站或网关", kind: "openai-compatible", category: "aggregator", badge: "聚合", base_url: "", model: "", hue: 250 },
  { id: "ollama", name: "Ollama", desc: "本地开源模型运行时", kind: "ollama", category: "local", badge: "本地", base_url: "http://127.0.0.1:11434", model: "qwen2.5-coder:14b", hue: 205 },
];

const TABS: Array<{ key: Category | "recommended"; label: string }> = [
  { key: "recommended", label: "推荐" },
  { key: "account", label: "账号" },
  { key: "plan", label: "模型计划" },
  { key: "api", label: "API" },
  { key: "aggregator", label: "聚合服务" },
  { key: "local", label: "本地" },
];

function hueFor(id: string): number {
  if (id === "env") return 150;
  return CATALOG.find((entry) => entry.id === id)?.hue ?? 250;
}

export function BrandTile({ name, hue, size = 36 }: { name: string; hue: number; size?: number }) {
  return (
    <span
      className="brand-tile"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.42), ["--hue" as string]: String(hue) }}
    >
      {name.charAt(0).toUpperCase()}
    </span>
  );
}

export function ModelsPage(props: {
  models: ModelInfo[];
  activeModel: string;
  onModel: (id: string) => void;
  onChanged: () => Promise<void>;
  showToast: (message: string) => void;
}) {
  const [detailId, setDetailId] = useState<string | null>(null);
  const [connectEntry, setConnectEntry] = useState<CatalogEntry | null>(null);
  const [tab, setTab] = useState<Category | "recommended">("recommended");
  const [query, setQuery] = useState("");

  const connected = props.models.filter((m) => m.has_key || m.kind === "ollama" || m.custom);
  const detail = props.models.find((m) => m.id === detailId) || null;

  const catalog = useMemo(() => {
    const inTab = CATALOG.filter((entry) => (tab === "recommended" ? true : entry.category === tab));
    const q = query.trim().toLowerCase();
    return q
      ? inTab.filter((entry) => entry.name.toLowerCase().includes(q) || entry.desc.toLowerCase().includes(q))
      : inTab;
  }, [tab, query]);

  if (detail) {
    return (
      <ProviderDetail
        model={detail}
        active={props.activeModel === detail.id}
        onBack={() => setDetailId(null)}
        onModel={props.onModel}
        onChanged={props.onChanged}
        showToast={props.showToast}
      />
    );
  }

  return (
    <div className="settings-page-inner">
      <header className="page-heading">
        <h1>模型</h1>
        <p>模型连接、API key 与凭据管理。</p>
      </header>

      <section className="settings-block">
        <div className="block-head">
          <h3>已连接<span className="quiet">{connected.length} 个连接</span></h3>
        </div>
        <p className="block-help">管理默认模型、凭据与需要处理的连接状态。</p>
        <div className="connected-list">
          {connected.map((model) => (
            <button key={model.id} className="connected-row" onClick={() => setDetailId(model.id)}>
              <BrandTile name={model.name} hue={hueFor(model.id)} />
              <span className="row-copy">
                <strong>
                  {model.name}
                  {props.activeModel === model.id && <span className="pill default-pill">默认</span>}
                  {!model.has_key && model.kind !== "ollama" && <span className="pill warn-pill">缺少凭据</span>}
                </strong>
                <small>{model.model}{model.base_url ? ` · ${model.base_url}` : ""}</small>
              </span>
              <ChevronRight size={16} />
            </button>
          ))}
          {!connected.length && <EmptyPanel icon={<KeyRound />} text="还没有连接，从下方添加一个模型连接" />}
        </div>
      </section>

      <div className="block-divider" />

      <section className="settings-block">
        <div className="block-head"><h3>添加新连接</h3></div>
        <p className="block-help">选择 API、聚合服务或本地运行时。</p>
        <div className="catalog-tabs" role="tablist" aria-label="模型供应商分类">
          {TABS.map((item) => (
            <button
              key={item.key}
              role="tab"
              aria-selected={tab === item.key}
              className={tab === item.key ? "active" : ""}
              onClick={() => setTab(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <label className="catalog-search">
          <Search size={15} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索服务商"
            aria-label="搜索模型服务商"
          />
        </label>
        {tab === "account" || tab === "plan" ? (
          <p className="catalog-empty">GraphCoder 当前版本通过 API key 与本地运行时连接模型，账号登录类连接即将支持。</p>
        ) : (
          <div className="catalog-list">
            {catalog.map((entry) => {
              const existing = props.models.find((m) => m.id === entry.id && (m.has_key || m.custom));
              return (
                <button
                  key={entry.id}
                  className="catalog-row"
                  onClick={() => (existing ? setDetailId(entry.id) : setConnectEntry(entry))}
                >
                  <BrandTile name={entry.name} hue={entry.hue} />
                  <span className="row-copy">
                    <strong>{entry.name}</strong>
                    <small>{entry.desc}</small>
                  </span>
                  {existing ? <span className="pill ready-pill">已连接</span> : <span className="pill">{entry.badge}</span>}
                  <ChevronRight size={15} />
                </button>
              );
            })}
            {!catalog.length && <p className="catalog-empty">没有匹配的服务商</p>}
          </div>
        )}
      </section>

      {connectEntry && (
        <ConnectDialog
          entry={connectEntry}
          onClose={() => setConnectEntry(null)}
          showToast={props.showToast}
          onConnected={async (id, setDefault) => {
            await props.onChanged();
            if (setDefault) await props.onModel(id);
            setConnectEntry(null);
          }}
        />
      )}
    </div>
  );
}

function ConnectDialog(props: {
  entry: CatalogEntry;
  onClose: () => void;
  onConnected: (id: string, setDefault: boolean) => Promise<void>;
  showToast: (message: string) => void;
}) {
  const [form, setForm] = useState<ProviderInput>({
    name: props.entry.id === "custom-openai" ? "" : props.entry.name,
    kind: props.entry.kind,
    model: props.entry.model || "",
    base_url: props.entry.base_url || "",
    api_key: "",
    api_key_env: "",
    temperature: 0.7,
    max_tokens: 8192,
  });
  const [setDefault, setSetDefault] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);
  const lockUrl = props.entry.kind !== "openai-compatible";

  const save = async () => {
    setSaving(true);
    try {
      const saved = await api.upsertProvider(form);
      props.showToast(`已连接 ${saved.name}`);
      await props.onConnected(saved.id, setDefault);
    } catch (reason) {
      props.showToast(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.testProvider({ ...form }));
    } catch (reason) {
      setTestResult({ ok: false, latency_ms: 0, detail: "", error: reason instanceof Error ? reason.message : String(reason) });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={props.onClose}>
      <div className="connect-dialog" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <BrandTile name={props.entry.name || "自"} hue={props.entry.hue} size={34} />
          <div className="dialog-title">
            <strong>{props.entry.name}</strong>
            <small>{props.entry.desc}</small>
          </div>
          <IconButton label="关闭" onClick={props.onClose}><X size={16} /></IconButton>
        </header>
        <div className="connect-fields">
          <label>连接名称
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="例如：我的中转站" />
          </label>
          <label>Base URL
            <input
              value={form.base_url}
              disabled={lockUrl}
              onChange={(event) => setForm({ ...form, base_url: event.target.value })}
              placeholder={lockUrl ? "服务商默认地址" : "https://api.example.com/v1"}
            />
          </label>
          <label>默认模型
            <input value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} placeholder="例如 gpt-4o、claude-sonnet-4-5" />
          </label>
          {props.entry.kind !== "ollama" && (
            <label>API Key
              <input type="password" value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} placeholder="留空则尝试环境变量" />
            </label>
          )}
          <div className="field-row">
            <label>Temperature
              <input type="number" step="0.1" value={String(form.temperature ?? 0.7)} onChange={(event) => setForm({ ...form, temperature: Number(event.target.value) })} />
            </label>
            <label>Max Tokens
              <input type="number" value={String(form.max_tokens ?? 8192)} onChange={(event) => setForm({ ...form, max_tokens: Number(event.target.value) })} />
            </label>
          </div>
          <label className="check-row">
            <input type="checkbox" checked={setDefault} onChange={(event) => setSetDefault(event.target.checked)} />
            保存后设为默认模型
          </label>
          {testResult && (
            <p className={testResult.ok ? "test-ok" : "test-fail"}>
              {testResult.ok ? `连接成功（${testResult.latency_ms}ms）` : `连接失败：${testResult.error}`}
            </p>
          )}
        </div>
        <footer>
          <button className="quiet-button" disabled={testing} onClick={test}>
            {testing ? <Loader2 size={15} className="spin" /> : <KeyRound size={15} />}测试连接
          </button>
          <span className="spacer" />
          <button className="quiet-button" onClick={props.onClose}>取消</button>
          <button className="primary-button" disabled={saving || !form.name.trim() || !form.model.trim()} onClick={save}>
            <Save size={15} />{saving ? "保存中" : "保存并连接"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function ProviderDetail(props: {
  model: ModelInfo;
  active: boolean;
  onBack: () => void;
  onModel: (id: string) => void;
  onChanged: () => Promise<void>;
  showToast: (message: string) => void;
}) {
  const editable = props.model.custom;
  const [form, setForm] = useState<ProviderInput>({
    id: props.model.id,
    name: props.model.name,
    kind: props.model.kind,
    model: props.model.model,
    base_url: props.model.base_url || "",
    api_key: "",
    api_key_env: "",
    temperature: props.model.temperature ?? 0.7,
    max_tokens: props.model.max_tokens ?? 8192,
  });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [catalog, setCatalog] = useState<ModelInfo[]>([]);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);

  const status = props.model.kind === "ollama"
    ? "本地运行时"
    : props.model.has_key ? "凭据就绪" : "缺少凭据";

  const test = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.testProvider(editable ? { ...form } : { id: props.model.id }));
    } catch (reason) {
      setTestResult({ ok: false, latency_ms: 0, detail: "", error: reason instanceof Error ? reason.message : String(reason) });
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.upsertProvider(form);
      await props.onChanged();
      props.showToast("已保存连接修改");
    } catch (reason) {
      props.showToast(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`删除模型连接“${props.model.name}”？`)) return;
    await api.deleteProvider(props.model.id);
    await props.onChanged();
    props.showToast(`已删除模型连接: ${props.model.name}`);
    props.onBack();
  };

  const fetchCatalog = async () => {
    setFetching(true);
    try {
      const data = await api.fetchModels(props.model.id);
      setCatalog(data.models);
      if (!data.models.length) props.showToast("未抓取到模型目录，请检查凭据与网络");
    } catch (reason) {
      props.showToast(reason instanceof Error ? reason.message : "抓取模型目录失败");
    } finally {
      setFetching(false);
    }
  };

  return (
    <div className="settings-page-inner">
      <button className="back-row" onClick={props.onBack}><ArrowLeft size={15} />返回模型</button>
      <div className="detail-head">
        <BrandTile name={props.model.name} hue={hueFor(props.model.id)} size={44} />
        <div className="dialog-title">
          <strong>
            {props.model.name}
            {props.active && <span className="pill default-pill">默认</span>}
          </strong>
          <small>{props.model.kind}{props.model.base_url ? ` · ${props.model.base_url}` : ""}</small>
        </div>
        <span className={props.model.has_key || props.model.kind === "ollama" ? "pill ready-pill" : "pill warn-pill"}>{status}</span>
      </div>

      <SettingsSection
        title="连接配置"
        description={
          editable
            ? "编辑此连接的凭据、地址与默认模型。"
            : "内置连接的凭据来自环境变量或 .env；如需独立凭据，请通过添加新连接创建自定义连接。"
        }
      >
        <div className="connect-fields">
          <label>连接名称
            <input value={form.name} disabled={!editable} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </label>
          <label>Base URL
            <input value={form.base_url} disabled={!editable || props.model.kind !== "openai-compatible"} onChange={(event) => setForm({ ...form, base_url: event.target.value })} placeholder="服务商默认地址" />
          </label>
          <label>默认模型
            <input value={form.model} disabled={!editable} onChange={(event) => setForm({ ...form, model: event.target.value })} />
          </label>
          {editable && (
            <>
              <label>API Key
                <input type="password" value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} placeholder="留空保持当前凭据" />
              </label>
              <label>API Key 环境变量名
                <input value={form.api_key_env} onChange={(event) => setForm({ ...form, api_key_env: event.target.value })} placeholder="例如 OPENAI_API_KEY" />
              </label>
            </>
          )}
          <div className="field-row">
            <label>Temperature
              <input type="number" step="0.1" value={String(form.temperature ?? 0.7)} disabled={!editable} onChange={(event) => setForm({ ...form, temperature: Number(event.target.value) })} />
            </label>
            <label>Max Tokens
              <input type="number" value={String(form.max_tokens ?? 8192)} disabled={!editable} onChange={(event) => setForm({ ...form, max_tokens: Number(event.target.value) })} />
            </label>
          </div>
          {editable && props.model.kind === "openai-compatible" && !!catalog.length && (
            <label>模型目录
              <select value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })}>
                {catalog.map((item) => <option key={item.id} value={item.model}>{item.model}</option>)}
              </select>
            </label>
          )}
          {testResult && (
            <p className={testResult.ok ? "test-ok" : "test-fail"}>
              {testResult.ok ? `连接成功（${testResult.latency_ms}ms）${testResult.detail ? `：${testResult.detail}` : ""}` : `连接失败：${testResult.error}`}
            </p>
          )}
        </div>
        <div className="detail-actions">
          {!props.active && (
            <button className="primary-button" disabled={!props.model.has_key && !editable} onClick={() => props.onModel(props.model.id)}>
              设为默认
            </button>
          )}
          <button className="quiet-button" disabled={testing} onClick={test}>
            {testing ? <Loader2 size={15} className="spin" /> : <KeyRound size={15} />}测试连接
          </button>
          {editable && props.model.kind === "openai-compatible" && (
            <button className="quiet-button" disabled={fetching} onClick={fetchCatalog}>
              {fetching ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}拉取模型目录
            </button>
          )}
          {editable && (
            <button className="primary-button" disabled={saving || !form.name.trim() || !form.model.trim()} onClick={save}>
              <Save size={15} />{saving ? "保存中" : "保存修改"}
            </button>
          )}
          <span className="spacer" />
          {editable && (
            <IconButton label="删除连接" className="danger-button" onClick={remove}><Trash2 size={15} /></IconButton>
          )}
        </div>
      </SettingsSection>
    </div>
  );
}
