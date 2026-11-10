const BADGE_STYLES: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  published: "bg-emerald-50 text-emerald-700 border-emerald-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  draft: "bg-sky-50 text-sky-700 border-sky-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  outdated: "bg-amber-50 text-amber-800 border-amber-200",
  inactive: "bg-slate-100 text-slate-600 border-slate-200",
  deleted: "bg-slate-100 text-slate-500 border-slate-200",
  failed: "bg-rose-50 text-rose-700 border-rose-200",
  admin: "bg-teal-50 text-[#075D6B] border-teal-200",
  customer: "bg-slate-100 text-[#173042] border-slate-200",
  led: "bg-emerald-50 text-emerald-700 border-emerald-200",
  non_led: "bg-slate-100 text-slate-700 border-slate-200",
};

const LABELS: Record<string, string> = {
  active: "Active",
  inactive: "Inactive",
  published: "Published",
  draft: "Draft",
  outdated: "Outdated (Regenerate)",
  failed: "Failed",
  success: "Success",
  warning: "With Warnings",
  superseded: "Superseded",
  deleted: "Deleted",
  admin: "Administrator",
  customer: "Customer",
  led: "LED",
  non_led: "Non-LED",
};

export function StatusBadge({
  status,
  label,
}: {
  status: string;
  label?: string;
}) {
  const key = status.toLowerCase();
  const style = BADGE_STYLES[key] || "bg-slate-100 text-slate-700 border-slate-200";
  const text = label || LABELS[key] || status;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style}`}
    >
      {text}
    </span>
  );
}

