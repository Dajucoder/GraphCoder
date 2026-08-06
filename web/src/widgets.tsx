/* Shared settings widgets: section shells, permission and memory managers. */

import { useState } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Brain, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "./api";
import type { MemoryEntry, PermissionRule, SettingsInfo } from "./api";

export function IconButton(props: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  const { label, className = "", children, ...rest } = props;
  return (
    <button className={`icon-button ${className}`} title={label} aria-label={label} {...rest}>
      {children}
    </button>
  );
}

export function SettingsSection(props: { title: string; description: string; children: ReactNode }) {
  return (
    <div className="settings-section">
      <header>
        <h3>{props.title}</h3>
        <p>{props.description}</p>
      </header>
      {props.children}
    </div>
  );
}

export function PageHeading({ title, description }: { title: string; description: string }) {
  return (
    <header className="page-heading">
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

export function EmptyPanel({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="empty-panel">
      {icon}
      <span>{text}</span>
    </div>
  );
}

export function actionName(action: string) {
  return ({ allow: "允许", ask: "询问", deny: "拒绝" } as Record<string, string>)[action] || action;
}

export function PermissionManager(props: {
  settings: SettingsInfo;
  onSettings: (settings: SettingsInfo) => void;
}) {
  const [form, setForm] = useState({ kind: "command", pattern: "", action: "ask" });
  const refresh = async () => {
    const next = await api.getSettings();
    props.onSettings(next);
  };
  return (
    <SettingsSection title="权限规则" description="控制命令、工具和目录在执行前的审批方式">
      <div className="permission-form">
        <select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value })}>
          <option value="command">命令</option>
          <option value="tool">工具</option>
          <option value="dir">目录</option>
        </select>
        <input
          value={form.pattern}
          onChange={(event) => setForm({ ...form, pattern: event.target.value })}
          placeholder="匹配规则，例如 git push*"
        />
        <select value={form.action} onChange={(event) => setForm({ ...form, action: event.target.value })}>
          <option value="ask">询问</option>
          <option value="allow">允许</option>
          <option value="deny">拒绝</option>
        </select>
        <button
          disabled={!form.pattern.trim()}
          onClick={async () => {
            await api.addPermission(form.kind, form.pattern.trim(), form.action);
            setForm({ ...form, pattern: "" });
            await refresh();
          }}
        >
          <Plus />添加
        </button>
      </div>
      <div className="permission-rules">
        {props.settings.permissions.map((rule: PermissionRule) => (
          <div key={rule.id}>
            <span className={`rule-action ${rule.action}`}>{actionName(rule.action)}</span>
            <code>{rule.kind}: {rule.pattern}</code>
            <IconButton
              label="删除规则"
              onClick={async () => {
                await api.removePermission(rule.id);
                await refresh();
              }}
            >
              <Trash2 />
            </IconButton>
          </div>
        ))}
        {!props.settings.permissions.length && <EmptyPanel icon={<ShieldCheck />} text="还没有自定义权限规则" />}
      </div>
    </SettingsSection>
  );
}

export function MemoryManager(props: {
  entries: MemoryEntry[];
  threadId: string;
  onChanged: () => void;
  showToast: (message: string) => void;
  standalone?: boolean;
}) {
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const body = (
    <>
      <div className="memory-form">
        <input value={key} onChange={(event) => setKey(event.target.value)} placeholder="名称" />
        <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="希望 GraphCoder 记住的内容" />
        <button
          disabled={!props.threadId || !key.trim() || !value.trim()}
          onClick={async () => {
            await api.memoryAdd(props.threadId, key.trim(), value.trim());
            setKey("");
            setValue("");
            props.onChanged();
            props.showToast("记忆已保存");
          }}
        >
          <Plus />添加
        </button>
      </div>
      <div className="memory-entries">
        {props.entries.map((entry) => (
          <div key={entry.id}>
            <Brain />
            <span><strong>{entry.key}</strong><p>{entry.value}</p></span>
            <IconButton
              label="删除记忆"
              onClick={async () => {
                await api.memoryDelete(entry.id);
                props.onChanged();
              }}
            >
              <Trash2 />
            </IconButton>
          </div>
        ))}
        {!props.entries.length && <EmptyPanel icon={<Brain />} text="当前会话还没有记忆" />}
      </div>
    </>
  );
  if (props.standalone) {
    return (
      <div className="module-page">
        <PageHeading title="记忆" description="让 GraphCoder 在后续回合中保留重要上下文" />
        {body}
      </div>
    );
  }
  return <SettingsSection title="会话记忆" description="保存在本机，仅供当前会话的 Agent 使用">{body}</SettingsSection>;
}
