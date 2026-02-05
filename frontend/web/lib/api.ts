const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

if (!API_BASE) {
  console.error("NEXT_PUBLIC_API_BASE_URL is not set");
}

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type Citation = {
  title?: string | null;
  source?: string | null;
  url?: string | null;
  snippet?: string | null;
};

export type ChatResponse = {
  conversation_id: number;
  reply: string;
  chat_message_id: number;
  citations?: Citation[];

  // 🔴 SAFETY META
  risk_level?: string;
  emergency_detected?: boolean;
  confidence_score?: number;
  suppression_reason?: string;
  model_mode?: "online" | "offline";
};

/**
 * Matches backend ExplainResponse in chat.py:
 * payload = {
 *   chat_message_id,
 *   risk_level,
 *   emergency_detected,
 *   risk_reason,
 *   risk_trigger,
 *   primary_domain,
 *   all_domains,
 *   model_name,
 *   created_at,
 *   confidence_score,
 *   reasoning_summary
 * }
 */
export type ExplainResponse = {
  chat_message_id: number;

  risk_level: string;
  emergency_detected: boolean;

  risk_reason: string;
  risk_trigger?: string | null;

  primary_domain?: string | null;
  all_domains?: string[] | null;

  model_name?: string | null;
  created_at?: string | null;

  confidence_score?: number | null;
  reasoning_summary?: string | null;

  suppression_reason?: string;
};

/**
 * Backend explain-rag returns:
 * {
 *   chat_message_id: number,
 *   role: string,
 *   rag: { ... }
 * }
 */
export type ExplainRagResponse = {
  chat_message_id: number;
  role: "user" | "assistant";
  rag: {
    rag_confidence?: number | null;
    model_confidence?: number | null;
    final_confidence?: number | null;
    citations_returned?: boolean | null;
    suppression_reason?: string | null;
    retrieved_chunks?: Array<{
      chunk_id?: number | null;
      chunk_number?: number | null;
      document_id?: number | null;
      title?: string | null;
      source?: string | null;
      source_file?: string | null;
      page_number?: number | null;
      medical_domain?: string | null;
      authority_level?: string | null;
    }>;
  } | null;
};

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("medibot_token");
}

export function setToken(token: string) {
  localStorage.setItem("medibot_token", token);
}

export function clearToken() {
  localStorage.removeItem("medibot_token");
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    // FastAPI often returns: { detail: "..." } or { detail: [...] }
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) return JSON.stringify(data.detail);
    return JSON.stringify(data);
  } catch {
    try {
      const text = await res.text();
      return text || `Request failed: ${res.status}`;
    } catch {
      return `Request failed: ${res.status}`;
    }
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  auth: boolean = false
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  // Only set JSON header when we actually send JSON
  if (!headers["Content-Type"] && options.body) {
    headers["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = getToken();
    if (!token) throw new Error("Not authenticated");
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const msg = await readErrorMessage(res);
    throw new Error(msg);
  }

  return res.json() as Promise<T>;
}

export async function register(email: string, password: string) {
  const res = await fetch(
    `${API_BASE}/api/v1/auth/register`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || "Registration failed");
  }

  return res.json();
}

export async function login(email: string, password: string) {
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);

  const res = await fetch(
    `${API_BASE}/api/v1/auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: params.toString(),
    }
  );

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || "Invalid email or password");
  }

  const data = await res.json();
  setToken(data.access_token); // ✅ FIX
  return data;
}

export async function sendChat(message: string, conversation_id?: number) {
  return apiFetch<ChatResponse>(
    `/api/v1/chat`,
    {
      method: "POST",
      body: JSON.stringify({ message, conversation_id }),
    },
    true
  );
}

export async function explain(chat_message_id: number) {
  return apiFetch<ExplainResponse>(
    `/api/v1/chat/${chat_message_id}/explain`,
    { method: "GET" },
    true
  );
}

export async function explainRag(chat_message_id: number) {
  return apiFetch<ExplainRagResponse>(
    `/api/v1/chat/${chat_message_id}/explain-rag`,
    { method: "GET" },
    true
  );
}

export async function listConversations() {
  return apiFetch<
    { id: number; title: string; created_at: string; updated_at: string }[]
  >(`/api/v1/conversations`, { method: "GET" }, true);
}

export async function getConversation(conversation_id: number) {
  return apiFetch<{
    id: number;
    title: string;
    messages: { id: number; role: string; content: string; created_at: string }[];
  }>(`/api/v1/conversations/${conversation_id}`, { method: "GET" }, true);
}

export async function escalateToDoctor(chat_message_id: number) {
  return apiFetch<{ status: string }>(
    `/api/v1/chat/${chat_message_id}/escalate`,
    { method: "POST" },
    true
  );
}

export async function listEscalations() {
  return apiFetch<{
    id: number;
    conversation_id: number;
    reason: string;
    notes: string;
    resolved: boolean;
    created_at: string;
  }[]>(`/api/v1/escalations`, { method: "GET" }, true);
}

export async function resolveEscalation(id: number) {
  return apiFetch<{ id: number; resolved: boolean }>(
    `/api/v1/escalations/${id}/resolve`,
    { method: "PATCH" },
    true
  );
}
