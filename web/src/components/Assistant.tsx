import { Loader2, Send, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";

interface Message {
  role: "user" | "assistant";
  text: string;
  tools?: string[];
}

const SUGGESTIONS = [
  "Which of my documents expire soon?",
  "Mujhe passport renew karna hai, kya chahiye?",
  "Is my name the same on all documents?",
  "Link PAN with Aadhaar: what do I need?",
];

// One conversation per browser tab session; the server keeps its memory per thread.
const THREAD_ID = crypto.randomUUID().slice(0, 32);

export default function Assistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.health().then((h) => setConfigured(h.llm_configured)).catch(() => setConfigured(false));
  }, []);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chat(text, THREAD_ID);
      setMessages((m) => [...m, { role: "assistant", text: res.reply, tools: res.tools_used }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: `⚠️ ${e instanceof Error ? e.message : e}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col">
      {configured === false && (
        <p className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          The assistant needs an LLM API key. Add <code>GOOGLE_API_KEY</code> or{" "}
          <code>ANTHROPIC_API_KEY</code> to <code>backend/.env</code> and restart the backend.
        </p>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto pb-3">
        {messages.length === 0 && (
          <div className="space-y-2 pt-4">
            <p className="text-sm text-slate-500">Ask about your documents. Try:</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 hover:border-brand-500"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
                m.role === "user" ? "bg-brand-600 text-white" : "border border-slate-200 bg-white text-slate-800"
              }`}
            >
              {m.text}
              {m.tools && m.tools.length > 0 && (
                <p className="mt-2 flex items-center gap-1 text-xs text-slate-400">
                  <Wrench size={11} /> {m.tools.join(", ")}
                </p>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <p className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 size={14} className="animate-spin" /> Thinking…
          </p>
        )}
        <div ref={bottom} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 border-t border-slate-200 pt-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask in English or Hindi…"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        />
        <button className="btn-primary" disabled={busy || !input.trim()}>
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
