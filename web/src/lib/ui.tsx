import {
  BookUser,
  Car,
  CreditCard,
  FileQuestion,
  Fingerprint,
  IdCard,
  Leaf,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import type { Status } from "../api";

export const DOC_ICONS: Record<string, { icon: LucideIcon; tint: string }> = {
  AADHAAR: { icon: Fingerprint, tint: "bg-orange-50 text-orange-600 ring-orange-100" },
  PAN: { icon: CreditCard, tint: "bg-sky-50 text-sky-600 ring-sky-100" },
  DRIVING_LICENCE: { icon: IdCard, tint: "bg-violet-50 text-violet-600 ring-violet-100" },
  PASSPORT: { icon: BookUser, tint: "bg-indigo-50 text-indigo-600 ring-indigo-100" },
  RC: { icon: Car, tint: "bg-teal-50 text-teal-600 ring-teal-100" },
  VEHICLE_INSURANCE: { icon: ShieldCheck, tint: "bg-emerald-50 text-emerald-600 ring-emerald-100" },
  PUC: { icon: Leaf, tint: "bg-lime-50 text-lime-700 ring-lime-100" },
  UNKNOWN: { icon: FileQuestion, tint: "bg-slate-100 text-slate-500 ring-slate-200" },
};

export function docIcon(docType: string) {
  return DOC_ICONS[docType] ?? DOC_ICONS.UNKNOWN;
}

export const STATUS_STYLES: Record<Status, { pill: string; dot: string; label: string; accent: string }> = {
  valid: { pill: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-emerald-500", label: "Valid", accent: "border-l-emerald-400" },
  expiring: { pill: "bg-amber-50 text-amber-800 ring-amber-200", dot: "bg-amber-500", label: "Expiring soon", accent: "border-l-amber-400" },
  expired: { pill: "bg-red-50 text-red-700 ring-red-200", dot: "bg-red-500", label: "Expired", accent: "border-l-red-400" },
  none: { pill: "bg-slate-100 text-slate-600 ring-slate-200", dot: "bg-slate-400", label: "No expiry", accent: "border-l-slate-200" },
};

const DAY = 24 * 60 * 60 * 1000;

export function daysFromToday(iso: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(iso);
  d.setHours(0, 0, 0, 0);
  return Math.round((d.getTime() - today.getTime()) / DAY);
}

/** "in 21 days", "10 days ago", "today", "in 4 years" */
export function relativeDays(iso: string): string {
  const n = daysFromToday(iso);
  if (n === 0) return "today";
  const abs = Math.abs(n);
  let text: string;
  if (abs >= 365) {
    const years = Math.round(abs / 365);
    text = `${years} year${years > 1 ? "s" : ""}`;
  } else if (abs >= 60) {
    const months = Math.round(abs / 30);
    text = `${months} months`;
  } else {
    text = `${abs} day${abs > 1 ? "s" : ""}`;
  }
  return n > 0 ? `in ${text}` : `${text} ago`;
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export const TOOL_LABELS: Record<string, string> = {
  list_my_documents: "Checked your documents",
  get_document_details: "Read document details",
  find_expiring_documents: "Checked expiry dates",
  check_name_consistency: "Compared names",
  get_procedure_checklist: "Fetched the official checklist",
  add_reminder: "Added a reminder",
  list_reminders: "Checked reminders",
};
