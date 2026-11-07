import {
  AlertTriangle,
  ChevronDown,
  Clock,
  Eye,
  FileStack,
  Loader2,
  ShieldAlert,
  Trash2,
  Upload,
  UserX,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type DocType, type DocumentOut, type NamePair } from "../api";
import { STATUS_STYLES, docIcon, formatDate, relativeDays } from "../lib/ui";
import StatusBadge from "./StatusBadge";

const STATUS_ORDER = { expired: 0, expiring: 1, valid: 2, none: 3 } as const;

interface Props {
  demo?: boolean;
  onAsk?: (question: string) => void;
}

/** Documents whose name disagrees with the others: the label that appears in the most mismatched pairs. */
function nameOutliers(pairs: NamePair[]) {
  const bad = pairs.filter((p) => !p.match);
  if (bad.length === 0) return [];
  const counts = new Map<string, { name: string; n: number; others: Set<string> }>();
  for (const p of bad) {
    for (const [label, name, otherName] of [
      [p.a, p.name_a, p.name_b],
      [p.b, p.name_b, p.name_a],
    ] as const) {
      const entry = counts.get(label) ?? { name, n: 0, others: new Set<string>() };
      entry.n += 1;
      entry.others.add(otherName.toUpperCase());
      counts.set(label, entry);
    }
  }
  const max = Math.max(...[...counts.values()].map((c) => c.n));
  return [...counts.entries()]
    .filter(([, c]) => c.n === max)
    .map(([label, c]) => ({ label, name: c.name, count: c.n, others: [...c.others] }));
}

function Stat({ icon: Icon, label, value, tone }: { icon: typeof FileStack; label: string; value: number; tone: string }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <div className={`grid h-10 w-10 place-items-center rounded-xl ${tone}`}>
        <Icon size={18} />
      </div>
      <div>
        <p className="font-display text-2xl font-bold leading-none text-slate-900">{value}</p>
        <p className="mt-1 text-xs font-medium text-slate-500">{label}</p>
      </div>
    </div>
  );
}

function DocumentCard({ doc, demo, onDelete }: { doc: DocumentOut; demo: boolean; onDelete: (id: string) => void }) {
  const [open, setOpen] = useState(doc.status === "expired" || doc.status === "expiring");
  const { icon: Icon, tint } = docIcon(doc.doc_type);
  const status = STATUS_STYLES[doc.status];

  return (
    <article className={`card flex flex-col border-l-4 ${status.accent} p-0`}>
      <div className="flex items-start gap-3 p-5 pb-4">
        <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ring-1 ring-inset ${tint}`}>
          <Icon size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="truncate text-base font-bold text-slate-900">{doc.doc_label}</h3>
            <StatusBadge status={doc.status} />
          </div>
          <p className="mt-0.5 truncate text-sm text-slate-500">{doc.holder_name ?? doc.filename}</p>
          {doc.expiry_date && (
            <p
              className={`mt-2 inline-flex items-center gap-1.5 text-xs font-medium ${
                doc.status === "expired" ? "text-red-600" : doc.status === "expiring" ? "text-amber-700" : "text-slate-500"
              }`}
            >
              <Clock size={12} />
              {doc.status === "expired" ? "Expired" : "Expires"} {formatDate(doc.expiry_date)} · {relativeDays(doc.expiry_date)}
            </p>
          )}
        </div>
      </div>

      {doc.notes.length > 0 && (
        <div className="mx-5 mb-3 space-y-1 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">
          {doc.notes.map((n) => (
            <p key={n} className="flex items-start gap-1.5">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {n}
            </p>
          ))}
        </div>
      )}

      {open && doc.fields.length > 0 && (
        <dl className="mx-5 mb-4 grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl bg-slate-50 p-3.5">
          {doc.fields.map((f) => (
            <div key={f.key} className="min-w-0">
              <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{f.label}</dt>
              <dd className={`truncate text-sm font-semibold text-slate-800 ${f.sensitive ? "font-mono tracking-wide" : ""}`} title={f.value}>
                {f.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-auto flex items-center justify-between border-t border-slate-100 px-5 py-2.5">
        {doc.fields.length > 0 ? (
          <button
            onClick={() => setOpen((o) => !o)}
            className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-800"
          >
            {open ? "Hide details" : `Show ${doc.fields.length} extracted fields`}
            <ChevronDown size={14} className={`transition ${open ? "rotate-180" : ""}`} />
          </button>
        ) : (
          <span className="text-xs text-slate-400">No fields could be read</span>
        )}
        {!demo && (
          <div className="flex items-center gap-1">
            <a href={api.fileUrl(doc.id)} target="_blank" rel="noreferrer" className="btn-ghost px-2 py-1.5" title="View original">
              <Eye size={15} />
            </a>
            <button className="btn-ghost px-2 py-1.5" title="Delete" onClick={() => onDelete(doc.id)}>
              <Trash2 size={15} />
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

export default function Documents({ demo = false, onAsk }: Props) {
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [types, setTypes] = useState<DocType[]>([]);
  const [docType, setDocType] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpload, setLastUpload] = useState<DocumentOut | null>(null);
  const [pairs, setPairs] = useState<NamePair[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [list, names] = await Promise.all([api.documents(), api.nameCheck()]);
    setDocs(list);
    setPairs(names.pairs);
  }, []);

  useEffect(() => {
    api.docTypes().then(setTypes).catch(() => {});
    refresh()
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, [refresh]);

  const sorted = useMemo(
    () => [...docs].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]),
    [docs],
  );
  const outliers = useMemo(() => nameOutliers(pairs), [pairs]);
  const expired = docs.filter((d) => d.status === "expired").length;
  const expiring = docs.filter((d) => d.status === "expiring").length;

  async function onFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const doc = await api.upload(file, docType || undefined);
      setLastUpload(doc);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this document and its file?")) return;
    await api.remove(id);
    if (lastUpload?.id === id) setLastUpload(null);
    await refresh();
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat icon={FileStack} label="Documents" value={docs.length} tone="bg-brand-50 text-brand-600" />
        <Stat icon={ShieldAlert} label="Expired" value={expired} tone="bg-red-50 text-red-600" />
        <Stat icon={Clock} label="Expiring soon" value={expiring} tone="bg-amber-50 text-amber-600" />
        <Stat icon={UserX} label="Name issues" value={outliers.length} tone="bg-orange-50 text-orange-600" />
      </div>

      {!demo && (
        <section className="card">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Add a document</h2>
              <p className="mt-0.5 text-sm text-slate-500">
                Take a clear photo or upload a PDF. DocMitra detects the type, reads the fields and tracks expiry.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"
              >
                <option value="">Detect type automatically</option>
                {types
                  .filter((t) => t.code !== "UNKNOWN")
                  .map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.label}
                    </option>
                  ))}
              </select>
              <input
                ref={fileInput}
                type="file"
                accept="image/*,application/pdf"
                capture="environment"
                className="hidden"
                onChange={(e) => onFile(e.target.files?.[0])}
              />
              <button className="btn-primary" disabled={busy} onClick={() => fileInput.current?.click()}>
                {busy ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
                {busy ? "Reading document…" : "Scan / upload"}
              </button>
            </div>
          </div>
          {lastUpload && (
            <p className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">
              Read as <strong>{lastUpload.doc_label}</strong>
              {lastUpload.holder_name && <> for {lastUpload.holder_name}</>}.
            </p>
          )}
        </section>
      )}

      {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {outliers.length > 0 && (
        <section className="flex flex-col gap-3 rounded-2xl border border-orange-200 bg-gradient-to-r from-orange-50 to-amber-50 p-4 sm:flex-row sm:items-center">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-orange-100 text-orange-600">
            <UserX size={18} />
          </div>
          <div className="flex-1 text-sm text-orange-900">
            <p className="font-semibold">Name mismatch across documents</p>
            {outliers.map((o) => (
              <p key={o.label} className="mt-0.5 text-orange-800">
                Your <strong>{o.label}</strong> says <strong>{o.name}</strong>, but {o.count} other document
                {o.count > 1 ? "s" : ""} say <strong>{o.others.join(" / ")}</strong>. Mismatches often get applications
                and claims rejected.
              </p>
            ))}
          </div>
          {onAsk && (
            <button className="chip shrink-0" onClick={() => onAsk("How do I fix the name mismatch on my documents?")}>
              Ask how to fix it
            </button>
          )}
        </section>
      )}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card h-36 animate-pulse bg-slate-100/60" />
          ))}
        </div>
      ) : sorted.length === 0 ? (
        <div className="card py-12 text-center">
          <FileStack className="mx-auto text-slate-300" size={36} />
          <p className="mt-3 font-semibold text-slate-700">No documents yet</p>
          <p className="text-sm text-slate-500">Scan your first document to get started.</p>
        </div>
      ) : (
        <section className="grid gap-4 md:grid-cols-2">
          {sorted.map((d) => (
            <DocumentCard key={d.id} doc={d} demo={demo} onDelete={remove} />
          ))}
        </section>
      )}
    </div>
  );
}
