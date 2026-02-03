"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listEscalations, resolveEscalation } from "@/lib/api";

type Escalation = {
  id: number;
  conversation_id: number;
  reason: string;
  notes: string;
  resolved: boolean;
  created_at: string;
};

export default function EscalationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  async function load() {
    try {
      const data = await listEscalations();
      setItems(data);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load escalations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onResolve(id: number) {
    try {
      setResolvingId(id);
      await resolveEscalation(id);
      await load(); // refresh list
    } catch (e: any) {
      alert(e?.message ?? "Failed to resolve escalation");
    } finally {
      setResolvingId(null);
    }
  }

  if (loading) {
    return <main className="p-6 text-white">Loading escalations...</main>;
  }

  if (error) {
    return <main className="p-6 text-red-400">{error}</main>;
  }

  return (
    <main className="min-h-screen bg-black text-white p-6">
      <h1 className="text-2xl font-semibold mb-4">Doctor Escalations</h1>

      {items.length === 0 && (
        <div className="text-white/60">No escalations found.</div>
      )}

      <div className="space-y-3">
        {items.map((e) => (
          <div
            key={e.id}
            className="border border-white/10 rounded-xl p-4 hover:bg-white/5"
          >
            <div className="flex justify-between items-start">
              <div>
                <div className="font-medium">
                  Escalation #{e.id} • Conversation {e.conversation_id}
                </div>
                <div className="mt-1 text-sm text-white/70">
                  Reason: {e.reason}
                </div>
                {e.notes && (
                  <div className="mt-1 text-sm text-white/50">
                    {e.notes}
                  </div>
                )}
                <div className="mt-1 text-sm text-white/50">
                  {new Date(e.created_at).toLocaleString()}
                </div>
              </div>

              <div
                className={`text-xs px-2 py-1 rounded ${
                  e.resolved ? "bg-green-600/30" : "bg-yellow-600/30"
                }`}
              >
                {e.resolved ? "Resolved" : "Pending"}
              </div>
            </div>

            <div className="mt-3 flex gap-2">
              {/* Open chat button */}
              <button
                onClick={() =>
                  router.push(`/chat?conversation=${e.conversation_id}`)
                }
                className="text-xs px-3 py-1 rounded border border-white/20 hover:bg-white/10"
              >
                Open conversation
              </button>

              {/* Resolve button */}
              {!e.resolved && (
                <button
                  onClick={() => onResolve(e.id)}
                  disabled={resolvingId === e.id}
                  className="text-xs px-3 py-1 rounded border border-green-500/40 hover:bg-green-500/10 disabled:opacity-50"
                >
                  {resolvingId === e.id ? "Resolving..." : "Mark as resolved"}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}


