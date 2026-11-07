import { AlertTriangle, CheckCircle2, Loader2, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type DocType, type DocumentOut, type NamePair } from "../api";
import StatusBadge from "./StatusBadge";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function Documents({ demo = false }: { demo?: boolean }) {
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [types, setTypes] = useState<DocType[]>([]);
  const [docType, setDocType] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastUpload, setLastUpload] = useState<DocumentOut | null>(null);
  const [mismatches, setMismatches] = useState<NamePair[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [list, names] = await Promise.all([api.documents(), api.nameCheck()]);
    setDocs(list);
    setMismatches(names.pairs.filter((p) => !p.match));
  }, []);

  useEffect(() => {
    api.docTypes().then(setTypes).catch(() => {});
    refresh().catch((e) => setError(String(e.message ?? e)));
  }, [refresh]);

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
    <div className="space-y-4">
      {!demo && (
      <section className="card space-y-3">
        <h2 className="font-semibold text-slate-900">Add a document</h2>
        <p className="text-sm text-slate-500">
          Take a clear photo or upload a PDF. DocMitra reads it, detects the type and tracks expiry dates.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
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
        {error && <p className="text-sm text-red-600">{error}</p>}
        {lastUpload && (
          <div className="rounded-lg bg-slate-50 p-3 text-sm">
            <p className="font-medium text-slate-800">
              Read as <span className="text-brand-700">{lastUpload.doc_label}</span>
              {lastUpload.holder_name && <> for {lastUpload.holder_name}</>}
            </p>
            {lastUpload.notes.map((n) => (
              <p key={n} className="mt-1 flex items-start gap-1.5 text-amber-700">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {n}
              </p>
            ))}
          </div>
        )}
      </section>
      )}

      {mismatches.length > 0 && (
        <section className="card border-amber-200 bg-amber-50">
          <h2 className="flex items-center gap-2 font-semibold text-amber-800">
            <AlertTriangle size={16} /> Name mismatch across documents
          </h2>
          <p className="mt-1 text-sm text-amber-800">
            Different spellings often get applications rejected. Consider getting these corrected:
          </p>
          <ul className="mt-2 space-y-1 text-sm text-amber-900">
            {mismatches.map((p) => (
              <li key={`${p.a}-${p.b}-${p.name_a}-${p.name_b}`}>
                {p.a}: <b>{p.name_a}</b> vs {p.b}: <b>{p.name_b}</b>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-3">
        {docs.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-500">No documents yet. Scan your first one above.</p>
        )}
        {docs.map((d) => (
          <article key={d.id} className="card">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="font-semibold text-slate-900">{d.doc_label}</h3>
                <p className="truncate text-sm text-slate-500">
                  {d.holder_name ?? d.filename}
                  {d.expiry_date && <> · expires {formatDate(d.expiry_date)}</>}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <StatusBadge status={d.status} />
{!demo && (
                <button className="btn-ghost px-2" title="Delete" onClick={() => remove(d.id)}>
                  <Trash2 size={16} />
                </button>
                )}
              </div>
            </div>
            {d.fields.length > 0 ? (
              <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-2">
                {d.fields.map((f) => (
                  <div key={f.key} className="flex justify-between gap-2 border-b border-slate-100 py-1">
                    <dt className="text-slate-500">{f.label}</dt>
                    <dd className="text-right font-medium text-slate-800">{f.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="mt-2 text-sm text-slate-400">No fields could be read from this file.</p>
            )}
            {!demo && (
              <a
                href={api.fileUrl(d.id)}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-xs text-brand-600 hover:underline"
              >
                <CheckCircle2 size={12} /> View original
              </a>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
