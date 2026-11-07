import { Bell, Bot, FileCheck2, FileText, Github, Lock, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "./api";
import Assistant from "./components/Assistant";
import Documents from "./components/Documents";
import Reminders from "./components/Reminders";

const TABS = [
  { id: "documents", label: "Documents", icon: FileText },
  { id: "reminders", label: "Reminders", icon: Bell },
  { id: "assistant", label: "Assistant", icon: Bot },
] as const;

type Tab = (typeof TABS)[number]["id"];

const REPO = "https://github.com/AkshayTripathiAI/DocMitra";

const DEMO_QUESTIONS = [
  "Which documents need my attention?",
  "Mujhe passport renew karna hai, kya chahiye?",
  "Is my name the same on all documents?",
];

export default function App() {
  const [tab, setTabState] = useState<Tab>(() => {
    const fromHash = window.location.hash.slice(1);
    return TABS.some((t) => t.id === fromHash) ? (fromHash as Tab) : "documents";
  });

  function setTab(next: Tab) {
    setTabState(next);
    history.replaceState(null, "", `#${next}`);
  }
  const [demo, setDemo] = useState(false);
  const [question, setQuestion] = useState<string | null>(null);

  useEffect(() => {
    api.health().then((h) => setDemo(h.demo_mode)).catch(() => {});
  }, []);

  function ask(q: string) {
    setQuestion(q);
    setTab("assistant");
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3 pb-4 pt-6">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-indigo-600 text-white shadow-lg shadow-brand-500/30">
            <FileCheck2 size={22} />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight text-slate-900">
              Doc<span className="text-brand-600">Mitra</span>
            </h1>
            <p className="text-xs text-slate-500">Your paperwork, sorted.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full bg-white/80 px-3 py-1.5 text-xs font-medium text-slate-600 ring-1 ring-slate-200 sm:inline-flex">
            <Lock size={12} className="text-emerald-600" /> ID numbers stay masked
          </span>
          <a
            href={REPO}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700"
          >
            <Github size={13} /> Source
          </a>
        </div>
      </header>

      {demo && (
        <div className="mb-5 overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-r from-brand-50 via-white to-sky-50 p-4 shadow-soft">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-brand-600 text-white">
              <Sparkles size={16} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-slate-900">You're viewing a live demo</p>
              <p className="mt-0.5 text-sm text-slate-600">
                These are sample documents for a fictional person, so uploads are turned off.{" "}
                <a href={REPO} target="_blank" rel="noreferrer" className="font-medium text-brand-700 underline-offset-2 hover:underline">
                  Run it locally
                </a>{" "}
                to scan your own: OCR runs on your machine. Ask the assistant:
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {DEMO_QUESTIONS.map((q) => (
                  <button key={q} className="chip" onClick={() => ask(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <nav className="sticky top-3 z-10 mb-5">
        <div className="inline-flex rounded-2xl bg-white p-1 shadow-soft ring-1 ring-slate-200/80">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition ${
                tab === id ? "bg-brand-600 text-white shadow-sm" : "text-slate-500 hover:bg-slate-50 hover:text-slate-800"
              }`}
            >
              <Icon size={16} /> {label}
            </button>
          ))}
        </div>
      </nav>

      <main className="flex-1 pb-10">
        {tab === "documents" && <Documents demo={demo} onAsk={ask} />}
        {tab === "reminders" && <Reminders />}
        {tab === "assistant" && (
          <Assistant initialQuestion={question} onConsumed={() => setQuestion(null)} />
        )}
      </main>

      <footer className="border-t border-slate-200/70 py-5 text-center text-xs text-slate-400">
        Built by{" "}
        <a href="https://akshaytripathiai.vercel.app" target="_blank" rel="noreferrer" className="font-medium text-slate-500 hover:text-brand-700">
          Akshay Tripathi
        </a>{" "}
        · FastAPI · LangGraph · React. Procedures are guidance only; confirm on the official portal.
      </footer>
    </div>
  );
}
