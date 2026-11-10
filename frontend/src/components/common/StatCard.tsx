import type { LucideIcon } from "lucide-react";

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  accent = "teal",
  onClick,
}: {
  title: string;
  value: number | string;
  subtitle?: string;
  icon: LucideIcon;
  accent?: "teal" | "mid" | "bright" | "slate";
  onClick?: () => void;
}) {
  const iconBg =
    accent === "bright"
      ? "bg-[#18A6A0]/15 text-[#075D6B]"
      : accent === "mid"
      ? "bg-[#0D7780]/12 text-[#0D7780]"
      : accent === "slate"
      ? "bg-slate-100 text-[#173042]"
      : "bg-[#075D6B]/10 text-[#075D6B]";

  return (
    <div
      onClick={onClick}
      className={`group rounded-xl border border-slate-200/80 bg-white p-5 shadow-card transition-all duration-150 ${
        onClick ? "cursor-pointer hover:-translate-y-0.5 hover:border-[#18A6A0]/60 hover:shadow-md" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#718096]">{title}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-[#173042]">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-[#718096]">{subtitle}</p>}
        </div>
        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

