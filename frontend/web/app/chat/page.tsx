"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  clearToken,
  listConversations,
  sendChat,
  explain,
  explainRag,
  getConversation,
  escalateToDoctor,
  type ChatResponse,
  type ExplainResponse,
} from "@/lib/api";

type UIMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  chat_message_id?: number;
  citations?: {
    title?: string | null;
    source?: string | null;
    source_file?: string | null;
    page_number?: number | null;
  }[];
  emergency_detected?: boolean;
  risk_level?: string;
  confidence_score?: number;
  model_mode?: "online" | "offline";
};

export default function ChatPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const [conversations, setConversations] = useState<
    { id: number; title: string; created_at: string; updated_at: string }[]
  >([]);
  const [activeConversationId, setActiveConversationId] = useState<number | undefined>(undefined);

  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  // track manual escalations
  const [escalatedIds, setEscalatedIds] = useState<number[]>([]);

  // Explain drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedChatMessageId, setSelectedChatMessageId] = useState<number | null>(null);
  const [explainData, setExplainData] = useState<ExplainResponse | null>(null);
  const [ragData, setRagData] = useState<any>(null);
  const [showDev, setShowDev] = useState(false);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);

  // Load conversations
  useEffect(() => {
    (async () => {
      try {
        const list = await listConversations();
        setConversations(list);
      } catch {
        router.push("/login");
      }
    })();
  }, [router]);

  // If URL has ?conversation=ID, auto-load that conversation
  useEffect(() => {
    const convParam = searchParams.get("conversation");
    if (!convParam) return;

    const id = Number(convParam);
    if (Number.isNaN(id)) return;

    // set active and load messages
    setActiveConversationId(id);
    loadConversation(id);
  }, [searchParams]);

  // auto scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const title = useMemo(() => {
    const found = conversations.find((c) => c.id === activeConversationId);
    return found?.title ?? "New conversation";
  }, [conversations, activeConversationId]);

  const conversationRisk = useMemo(() => {
    const lastAssistant = [...messages]
      .reverse()
      .find((m) => m.role === "assistant");

    if (!lastAssistant) return "low";

    if (lastAssistant.emergency_detected) return "emergency";
    if (lastAssistant.risk_level === "high") return "high";

    return "low";
  }, [messages]);

  const hadPreviousEmergency = useMemo(() => {
    return messages.some(
      (m) => m.role === "assistant" && m.emergency_detected === true
    );
  }, [messages]);

  const isNonMedicalTurn = useMemo(() => {
    const lastUser = [...messages]
      .reverse()
      .find((m) => m.role === "user");

    if (!lastUser) return false;

    const t = lastUser.content.toLowerCase();
    return ["hi", "hello", "thanks", "thank you", "bye"].some((p) =>
      t.startsWith(p)
    );
  }, [messages]);

  async function refreshConversations() {
    try {
      const list = await listConversations();
      setConversations(list);
    } catch {}
  }

  async function loadConversation(conversationId: number) {
    try {
      const conv = await getConversation(conversationId);

      const mapped: UIMessage[] = (conv.messages || []).map((m) => ({
        id: String(m.id),
        role: m.role === "user" ? "user" : "assistant",
        content: m.content,
        chat_message_id: m.id,
      }));

      setMessages(mapped);
    } catch {
      setMessages([]);
    }
  }

  async function onSend() {
    const text = input.trim();
    if (!text || sending) return;

    setInput("");
    setSending(true);

    const userMsg: UIMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    const thinkingId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: thinkingId, role: "assistant", content: "Thinking..." },
    ]);

    try {
      const res: ChatResponse = await sendChat(text, activeConversationId);
      setActiveConversationId(res.conversation_id);

      const assistantMsg: UIMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.reply,
        chat_message_id: res.chat_message_id,
        citations: res.citations ?? [],
        emergency_detected: res.emergency_detected,
        risk_level: res.risk_level,
        confidence_score: res.confidence_score,
        model_mode: res.model_mode,
      };

      setMessages((prev) => prev.filter((m) => m.id !== thinkingId).concat(assistantMsg));
      await refreshConversations();
    } catch {
      setMessages((prev) =>
        prev
          .filter((m) => m.id !== thinkingId)
          .concat({
            id: crypto.randomUUID(),
            role: "assistant",
            content: "Something went wrong while sending your message. Please try again.",
          })
      );
    } finally {
      setSending(false);
    }
  }

  async function openExplain(chat_message_id: number) {
    setDrawerOpen(true);
    setSelectedChatMessageId(chat_message_id);
    setExplainData(null);
    setRagData(null);
    setExplainError(null);
    setExplainLoading(true);

    try {
      const data = await explain(chat_message_id);
      setExplainData(data);

      if (showDev) {
        const rag = await explainRag(chat_message_id);
        setRagData(rag);
      }
    } catch (err: any) {
      setExplainError(err?.message ?? "Failed to load explanation");
    } finally {
      setExplainLoading(false);
    }
  }

  async function toggleDevMode() {
    const next = !showDev;
    setShowDev(next);

    if (next && selectedChatMessageId) {
      try {
        const rag = await explainRag(selectedChatMessageId);
        setRagData(rag);
      } catch {}
    }
  }

  function logout() {
    clearToken();
    router.push("/login");
  }

  return (
    <main className="h-screen bg-black text-white flex">
      {/* Sidebar */}
      <aside className="w-[320px] border-r border-white/10 bg-white/5 p-4 hidden md:flex flex-col">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-white/60">AI Medibot</div>
            <div className="text-lg font-semibold">Conversations</div>
          </div>
          <button
            onClick={logout}
            className="text-xs rounded-lg border border-white/15 px-2 py-1 text-white/70 hover:bg-white/5"
          >
            Logout
          </button>
        </div>

        <button
          onClick={() => {
            setActiveConversationId(undefined);
            setMessages([]);
          }}
          className="mt-4 rounded-xl bg-white text-black py-2 font-medium"
        >
          + New Chat
        </button>

        <div className="mt-4 space-y-2 overflow-auto">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={async () => {
                setActiveConversationId(c.id);
                await loadConversation(c.id);
              }}
              className={`w-full text-left rounded-xl px-3 py-2 border ${
                activeConversationId === c.id
                  ? "border-white/30 bg-white/10"
                  : "border-white/10 hover:bg-white/5"
              }`}
            >
              <div className="text-sm font-medium truncate">{c.title}</div>
              <div className="text-xs text-white/50">ID: {c.id}</div>
            </button>
          ))}
        </div>
      </aside>

      {/* Chat area */}
      <section className="flex-1 flex flex-col">
        <header className="border-b border-white/10 bg-white/5 px-4 py-3 flex items-center justify-between">
          <div>
            <div className="text-sm text-white/60">Conversation</div>
            <div className="flex items-center gap-2">
              <div className="font-semibold">{title}</div>
              <span
                className={
                  conversationRisk === "emergency"
                    ? "text-red-400 text-xs font-semibold uppercase"
                    : conversationRisk === "high"
                    ? "text-orange-400 text-xs font-semibold uppercase"
                    : "text-green-400 text-xs font-semibold uppercase"
                }
              >
                {conversationRisk} risk
              </span>

              {conversationRisk !== "emergency" &&
               hadPreviousEmergency &&
               !isNonMedicalTurn && (
                <span className="text-yellow-400 text-xs font-semibold uppercase">
                  previous emergency
                </span>
              )}
           </div>
          </div>

          <button
            onClick={toggleDevMode}
            className={`text-xs rounded-lg border px-2 py-1 ${
              showDev ? "border-white/30 bg-white/10" : "border-white/15 text-white/70"
            }`}
          >
            {showDev ? "Dev Mode: ON" : "Dev Mode: OFF"}
          </button>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-white/50 text-sm">
              Ask a health question like:{" "}
              <span className="text-white">“What are symptoms of diabetes?”</span>
            </div>
          )}

          {messages.map((m) => {
            const isEmergency = m.emergency_detected === true;
            const isSelected = m.chat_message_id === selectedChatMessageId;

            return (
              <div
                key={m.id}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 border ${
                    m.role === "user"
                      ? "bg-white text-black border-white/20"
                      : isEmergency
                      ? "border-red-500/50 bg-red-500/10"
                      : isSelected
                      ? "bg-white/5 border-blue-400/60 ring-1 ring-blue-400/40"
                      : "bg-white/5 border-white/10"
                  }`}
                >
                  {/* Emergency banner */}
                  {isEmergency && (
                    <div className="mb-3 rounded-xl border border-red-500/40 bg-red-500/20 px-3 py-2 text-sm">
                      <div className="font-semibold text-red-300">
                        ⚠️ Medical emergency suspected
                      </div>
                      <div className="text-red-200 text-xs mt-1">
                        Please seek immediate medical care.
                      </div>

                      <div className="mt-2 flex gap-2">
                        <a
                          href="tel:112"
                          className="rounded-lg bg-red-500 text-black px-3 py-1 text-xs font-medium"
                        >
                          Call emergency services
                        </a>

                        <button
                          onClick={async () => {
                            if (!m.chat_message_id) return;
                            await escalateToDoctor(m.chat_message_id);
                            setEscalatedIds((prev) =>
                              prev.includes(m.chat_message_id!)
                                ? prev
                                : [...prev, m.chat_message_id!]
                            );
                          }}
                          disabled={escalatedIds.includes(m.chat_message_id ?? -1)}
                          className="rounded-lg border border-red-500/40 px-3 py-1 text-xs text-red-200 hover:bg-red-500/10 disabled:opacity-60"
                        >
                          {escalatedIds.includes(m.chat_message_id ?? -1)
                            ? "Doctor notified"
                            : "Contact a doctor"}
                        </button>
                      </div>

                      {m.chat_message_id && escalatedIds.includes(m.chat_message_id) && (
                        <div className="mt-2 text-xs text-red-200">
                          A clinician has been notified and will review this case.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Risk badge */}
                  {m.role === "assistant" && m.risk_level && !isEmergency && (
                    <div className="mb-2 text-[10px] uppercase tracking-wide">
                      <span
                        className={
                          m.risk_level === "high"
                            ? "text-orange-400 font-semibold"
                            : "text-green-400 font-semibold"
                        }
                      >
                        {m.risk_level} risk
                      </span>
                    </div>
                  )}

                  {/* Model mode badge */}
                  {m.role === "assistant" && m.model_mode && (
                    <div className="mb-2 text-[10px] uppercase tracking-wide">
                      <span
                        className={
                          m.model_mode === "offline"
                            ? "text-gray-400 font-semibold"
                            : "text-blue-400 font-semibold"
                        }
                      >
                        {m.model_mode === "offline" ? "Offline safe mode" : "Online AI"}
                      </span>
                    </div>
                  )}

                  {/* Content */}
                  <div className="whitespace-pre-wrap text-sm leading-relaxed">
                    {m.content}
                  </div>

                  {/* Confidence indicator */}
                  {m.role === "assistant" &&
                   typeof m.confidence_score === "number" && (
                    <div className="mt-2 text-[10px] text-white/50">
                      Confidence: {(m.confidence_score * 100).toFixed(0)}%
                    </div>
                  )}

                  {/* Low-confidence warning */}
                  {m.role === "assistant" &&
                   typeof m.confidence_score === "number" &&
                   m.confidence_score < 0.4 && (
                    <div className="mt-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-2 py-1 text-[10px] text-yellow-200">
                      Low confidence. Consider adding more details or consulting a healthcare professional.
                    </div>
                  )}

                  {/* Assistant extras */}
                  {m.role === "assistant" && (
                    <div className="mt-3 space-y-2">
                      {!isEmergency && m.citations && m.citations.length > 0 && (
                        <div className="text-xs text-white/60">
                          <div className="mb-1">Sources</div>
                          <div className="space-y-2">
                            {m.citations.map((c, idx) => (
                              <details
                                key={idx}
                                className="rounded-lg border border-white/10 bg-black/30 px-2 py-1"
                              >
                                <summary className="cursor-pointer">
                                  {c.title || c.source || "Source"}
                                </summary>

                                <div className="mt-1 text-[11px] text-white/50 space-y-0.5">
                                  {c.source && <div>Source: {c.source}</div>}
                                  {c.source_file && <div>File: {c.source_file}</div>}
                                  {c.page_number && <div>Page: {c.page_number}</div>}
                                </div>
                              </details>
                            ))}
                          </div>
                         </div>
                       )}

                      {m.chat_message_id && !isEmergency && (
                        <button
                          onClick={() => openExplain(m.chat_message_id!)}
                          className="text-xs rounded-lg border border-white/15 px-2 py-1 text-white/70 hover:bg-white/5"
                        >
                          Why this answer?
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-white/10 bg-white/5 p-4">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSend();
                }
              }}
              placeholder="Type your message..."
              rows={2}
              className="flex-1 resize-none rounded-xl bg-black/40 border border-white/10 px-3 py-2 outline-none focus:border-white/30"
            />
            <button
              onClick={onSend}
              disabled={sending || !input.trim()}
              className="rounded-xl bg-white text-black px-4 py-2 font-medium disabled:opacity-60"
            >
              {sending ? "..." : "Send"}
            </button>
          </div>
        </div>
      </section>

      {/* Explain Drawer */}
      {drawerOpen && (
        <div className="w-[380px] border-l border-white/10 bg-black/80 backdrop-blur p-4 hidden lg:block">
          <div className="flex items-center justify-between">
            <div className="font-semibold">Why this answer?</div>
            <button
              onClick={() => setDrawerOpen(false)}
              className="text-xs rounded-lg border border-white/15 px-2 py-1 text-white/70 hover:bg-white/5"
            >
              Close
            </button>
          </div>

          {explainLoading && <div className="mt-4 text-white/60 text-sm">Loading explanation...</div>}
          {explainError && (
            <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
              {explainError}
            </div>
          )}

          {explainData && (
            <div className="mt-4 space-y-4 text-sm">
              {explainData.suppression_reason === "emergency_override" && (
                <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-200">
                  Some technical details are intentionally limited because this response was
                  flagged as a medical emergency.
                </div>
              )}

              {typeof explainData.confidence_score === "number" &&
                explainData.confidence_score < 0.4 && (
                  <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 px-3 py-2 text-xs text-orange-200">
                    This answer has low confidence. Consider providing more details or
                    consulting a healthcare professional.
                  </div>
                )}

              <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                <div className="text-white/60 text-xs">Safety</div>
                <div className="mt-2">
                  <div>
                    Risk level:{" "}
                    <span
                      className={
                        explainData.risk_level === "emergency"
                          ? "text-red-400 font-semibold"
                          : explainData.risk_level === "high"
                          ? "text-orange-400"
                          : "text-green-400"
                      }
                    >
                      {explainData.risk_level}
                    </span>
                  </div>
                  <div>
                    Emergency: <span className="text-white">{String(explainData.emergency_detected)}</span>
                  </div>
                  {explainData.risk_trigger && (
                    <div>
                      Trigger: <span className="text-white">{explainData.risk_trigger}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                <div className="text-white/60 text-xs">Routing</div>
                <div className="mt-2">
                  <div>
                    Primary domain:{" "}
                    <span className="text-white">{explainData.primary_domain ?? "unknown"}</span>
                  </div>
                  <div>
                    Confidence:{" "}
                    <span className="text-white">{explainData.confidence_score ?? "n/a"}</span>
                  </div>
                </div>
              </div>

              {explainData.reasoning_summary && (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                  <div className="text-white/60 text-xs">Summary</div>
                  <div className="mt-2 whitespace-pre-wrap text-white/80">
                    {explainData.reasoning_summary}
                  </div>
                </div>
              )}

              {showDev && (
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                  <div className="text-white/60 text-xs">Retrieval (Dev)</div>

                  {!ragData && <div className="mt-2 text-white/60">Loading...</div>}

                  {ragData && (
                    <div className="mt-2 space-y-2">
                      <div className="text-xs text-white/60">
                        Retrieved chunks: {ragData?.rag?.retrieved_chunks?.length ?? 0}
                      </div>

                      <div className="max-h-[240px] overflow-auto space-y-2">
                        {(ragData?.rag?.retrieved_chunks || []).map((chunk: any, idx: number) => (
                          <div
                            key={idx}
                            className="text-xs text-white/70 border border-white/10 rounded-xl p-2"
                          >
                            {typeof chunk === "string" ? chunk : JSON.stringify(chunk)}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {!explainLoading && !explainData && !explainError && (
            <div className="mt-4 text-white/60 text-sm">
              Select an assistant message and click “Why this answer?”
            </div>
          )}
        </div>
      )}
    </main>
  );
}



