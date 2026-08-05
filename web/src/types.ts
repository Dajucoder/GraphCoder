export interface ProviderPublic {
  id: string;
  name: string;
  kind: string;
  base_url: string | null;
  model: string;
  temperature: number;
  max_tokens: number;
  has_key: boolean;
  key_source: string;
}

export interface SessionSummary {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  ts?: number;
}

export interface SessionDetail extends SessionSummary {
  messages: ChatMessage[];
}

export interface TaskInfo {
  id: string;
  session_id: string;
  mode: "chat" | "build";
  content: string;
  status: string;
  created_at: number;
  event_count: number;
}

export interface StreamEvent {
  type: string;
  ts?: number;
  message?: string;
  delta?: string;
  content?: string;
  name?: string;
  arguments?: Record<string, unknown>;
  result?: string;
  id?: string;
  agent?: string;
}

export interface Approval {
  id: string;
  command: string;
  task_id: string;
  status: string;
}
