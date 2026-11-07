import { Bell, Bot, FileText } from "lucide-react";
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

export default function App() {
  const [tab, setTab] = useState<Tab>("documents");
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    api.health().then((h) => setDemo(h.demo_mode)).catch(() => {});
  }, []);

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col">
      <header className="flex items-center justify-between px-4 pb-2 pt-5">
        <div>
          <h1 className="text-xl font-bold text-slate-900">DocMitra</h1>
          <p className="text-xs text-slate-500">Your paperwork, sorted.</p>
        </div>
      </header>

      {demo && (
        <div className="mx-4 mb-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs text-brand-800">
          <strong>Public demo.</strong> These are sample documents for a fictional person, so uploads are
          off. Try the Assistant: <em>"Which documents need attention?"</em> or{" "}
          <em>"Mujhe passport renew karna hai, kya chahiye?"</em>{" "}
          <a className="underline" href="https://github.com/AkshayTripathiAI/DocMitra" target="_blank" rel="noreferrer">
            Run it locally
          </a>{" "}
          to scan your own (OCR runs on your machine).
        </div>
      )}

      <nav className="sticky top-0 z-10 flex gap-1 border-b border-slate-200 bg-slate-50/95 px-4 backdrop-blur">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium ${
              tab === id
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </nav>

      <main className="flex-1 px-4 py-4">
        {tab === "documents" && <Documents demo={demo} />}
        {tab === "reminders" && <Reminders />}
        {tab === "assistant" && <Assistant />}
      </main>
    </div>
  );
}
