import { useEffect, useState } from "react";
import { api, type Reminder } from "../api";

export default function Reminders() {
  const [items, setItems] = useState<Reminder[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.reminders().then(setItems).catch((e) => setError(e.message));
  }, []);

  async function toggle(r: Reminder) {
    const updated = await api.setReminderDone(r.id, !r.done);
    setItems((all) => all.map((x) => (x.id === r.id ? updated : x)));
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (items.length === 0)
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        No reminders. They appear automatically when a document has an expiry date.
      </p>
    );

  return (
    <ul className="space-y-2">
      {items.map((r) => (
        <li key={r.id} className="card flex items-center gap-3">
          <input
            type="checkbox"
            checked={r.done}
            onChange={() => toggle(r)}
            className="h-4 w-4 accent-brand-600"
          />
          <div className={r.done ? "text-slate-400 line-through" : ""}>
            <p className="text-sm font-medium text-slate-800">{r.title}</p>
            <p className={`text-xs ${r.overdue ? "font-medium text-red-600" : "text-slate-500"}`}>
              {r.overdue ? "Overdue · " : "Due "}
              {new Date(r.due_date).toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
