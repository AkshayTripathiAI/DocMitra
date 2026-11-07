import type { Status } from "../api";

const STYLES: Record<Status, string> = {
  valid: "bg-emerald-50 text-emerald-700",
  expiring: "bg-amber-50 text-amber-700",
  expired: "bg-red-50 text-red-700",
  none: "bg-slate-100 text-slate-500",
};

const LABELS: Record<Status, string> = {
  valid: "Valid",
  expiring: "Expiring soon",
  expired: "Expired",
  none: "No expiry",
};

export default function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
