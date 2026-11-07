import { Bot, CheckCircle2, Loader2, Send, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { TOOL_LABELS } from "../lib/ui";
import Markdown from "./Markdown";

interface Message {
  role: "user" | "assistant";
  text: string;
  tools?: string[];
  error?: boolean;
}

const SUGGESTIONS = [
  "Which of my documents expire soon?",
  "Mujhe passport renew karna hai, kya chahiye?",
  "Is my name the same on all documents?",
  "Link PAN with Aadhaar: what do I need?",
];

// One conversation per browser tab session; the server keeps its memory per thread.
const THREAD_ID = crypto.randomUUID().slice(0, 32);

interface Props {
  initialQuestion?: string | null;
  onConsumed?: () => void;
}

export default function Assistant({ initialQuestion, onConsumed }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const lastAsked = useRef<string | null>(null);

  useEffect(() => {
    api.health().then((h) => setConfigured(h.llm_configured)).catch(() => setConfigured(false));
  }, []);

  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, and an effect must return nothing.
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chat(text, THREAD_ID);
      setMessages((m) => [...m, { role: "assistant", text: res.reply, tools: res.tools_used }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: e instanceof Error ? e.message : String(e), error: true }]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initialQuestion && lastAsked.current !== initialQuestion) {
      lastAsked.current = initialQuestion;
      send(initialQuestion);
      onConsumed?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  return (
    <div className="card flex h-[calc(100vh-14rem)] min-h-[480px] flex-col p-0">
      <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-3.5">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-indigo-600 text-white">
          <Bot size={18} />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-900">DocMitra assistant</p>
          <p className="text-xs text-slate-500">Answers from your documents · English, Hindi or Hinglish</p>
        </div>
      </div>

      {configured === false && (
        <p className="mx-5 mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
          The assistant needs an LLM API key. Add <code>GOOGLE_API_KEY</code>, <code>GROQ_API_KEY</code> or{" "}
          <code>ANTHROPIC_API_KEY</code> to <code>backend/.env</code> and restart the backend.
        </p>
      )}

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
        {messages.length === 0 && (
          <div className="mx-auto max-w-md pt-6 text-center">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600">
              <Bot size={26} />
            </div>
            <p className="mt-3 font-display text-lg font-bold text-slate-900">Namaste! How can I help?</p>
            <p className="mt-1 text-sm text-slate-500">
              I look at your actual documents before answering, and I never see full ID numbers.
            </p>
            <div className="mt-5 grid gap-2 text-left">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-700 transition hover:border-brand-300 hover:bg-brand-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end gap-2">
              <div className="max-w-[80%] rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-sm text-white shadow-sm">
                {m.text}
              </div>
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-200 text-slate-600">
                <User size={15} />
              </div>
            </div>
          ) : (
            <div key={i} className="flex gap-2">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-50 text-brand-600">
                <Bot size={15} />
              </div>
              <div className="max-w-[85%]">
                {m.tools && m.tools.length > 0 && (
                  <div className="mb-1.5 flex flex-wrap gap-1.5">
                    {[...new Set(m.tools)].map((t) => (
                      <span key={t} className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-100">
                        <CheckCircle2 size={11} /> {TOOL_LABELS[t] ?? t}
                      </span>
                    ))}
                  </div>
                )}
                <div
                  className={`rounded-2xl rounded-tl-md px-4 py-2.5 text-sm ${
                    m.error ? "bg-red-50 text-red-700 ring-1 ring-red-100" : "bg-slate-50 text-slate-800 ring-1 ring-slate-200/70"
                  }`}
                >
                  <Markdown text={m.text} />
                </div>
              </div>
            </div>
          ),
        )}

        {busy && (
          <div className="flex gap-2">
            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-50 text-brand-600">
              <Bot size={15} />
            </div>
            <div className="flex items-center gap-2 rounded-2xl rounded-tl-md bg-slate-50 px-4 py-2.5 text-sm text-slate-500 ring-1 ring-slate-200/70">
              <Loader2 size={14} className="animate-spin" /> Checking your documents…
            </div>
          </div>
        )}
        <div ref={bottom} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2 border-t border-slate-100 p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask in English or Hindi…"
          className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm transition focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100"
        />
        <button className="btn-primary px-4" disabled={busy || !input.trim()} aria-label="Send">
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
