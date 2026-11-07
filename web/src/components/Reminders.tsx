import { BellRing, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Reminder } from "../api";
import { daysFromToday, relativeDays } from "../lib/ui";

function DateBlock({ iso, tone }: { iso: string; tone: string }) {
  const d = new Date(iso);
  return (
    <div className={`flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-xl ${tone}`}>
      <span className="text-[10px] font-bold uppercase tracking-wide">
        {d.toLocaleDateString("en-IN", { month: "short" })}
      </span>
      <span className="font-display text-xl font-bold leading-none">{d.getDate()}</span>
    </div>
  );
}

export default function Reminders() {
  const [items, setItems] = useState<Reminder[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .reminders()
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function toggle(r: Reminder) {
    const updated = await api.setReminderDone(r.id, !r.done);
    setItems((all) => all.map((x) => (x.id === r.id ? updated : x)));
  }

  if (error) return <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>;
  if (loading) return <div className="card h-40 animate-pulse bg-slate-100/60" />;
  if (items.length === 0)
    return (
      <div className="card py-12 text-center">
        <BellRing className="mx-auto text-slate-300" size={36} />
        <p className="mt-3 font-semibold text-slate-700">No reminders yet</p>
        <p className="text-sm text-slate-500">They appear automatically when a document has an expiry date.</p>
      </div>
    );

  const open = items.filter((r) => !r.done);
  const done = items.filter((r) => r.done);

  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Upcoming · {open.length}</h2>
        <ul className="space-y-3">
          {open.map((r) => {
            const days = daysFromToday(r.due_date);
            const tone = r.overdue
              ? "bg-red-50 text-red-700"
              : days <= 30
                ? "bg-amber-50 text-amber-700"
                : "bg-brand-50 text-brand-700";
            return (
              <li key={r.id} className="card flex items-center gap-4 p-4">
                <DateBlock iso={r.due_date} tone={tone} />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-900">{r.title}</p>
                  <p className={`text-sm ${r.overdue ? "font-semibold text-red-600" : "text-slate-500"}`}>
                    {r.overdue ? `Overdue · was due ${relativeDays(r.due_date)}` : `Due ${relativeDays(r.due_date)}`}
                  </p>
                </div>
                <button
                  onClick={() => toggle(r)}
                  className="btn border border-slate-200 bg-white px-3 py-2 text-slate-600 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700"
                >
                  <Check size={15} /> Done
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      {done.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-slate-400">Completed · {done.length}</h2>
          <ul className="space-y-2">
            {done.map((r) => (
              <li key={r.id} className="flex items-center gap-3 rounded-xl bg-white/60 px-4 py-3 ring-1 ring-slate-200/70">
                <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-100 text-emerald-700">
                  <Check size={14} />
                </span>
                <p className="flex-1 text-sm text-slate-400 line-through">{r.title}</p>
                <button onClick={() => toggle(r)} className="text-xs font-semibold text-brand-700 hover:underline">
                  Undo
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
