import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ClipboardList,
  Clock,
  GitMerge,
  Lightbulb,
  MapPin,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { extractErrorMessage } from "../../services/api";
import { dashboardApi } from "../../services/endpoints";
import type { CustomerDashboardData } from "../../types";
import { formatDateTime, formatReportType } from "../../utils/format";
import { HierarchyExplorer } from "../../components/hierarchy/HierarchyExplorer";

export function CustomerDashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<CustomerDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dashboardApi
      .getCustomer()
      .then(setData)
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-[#718096]">
        Loading your asset reports portal...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
        {error || "Unable to load customer dashboard."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-[#075D6B] to-[#0D7780] p-6 text-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-teal-200">
              Customer Asset Reports Portal
            </p>
            <h1 className="mt-1 text-2xl font-bold">Welcome, {user?.name}</h1>
            <p className="mt-1 text-sm text-teal-100/90">
              Assigned Customer:{" "}
              <strong>
                {data.customer_names.length > 0
                  ? data.customer_names.join(", ")
                  : "No customer assigned"}
              </strong>{" "}
              • {data.total_regions} Regions • {data.total_zones} Zones
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2.5 text-xs">
            <Clock className="h-4 w-4 text-teal-200" />
            <div>
              <p className="text-teal-200">Last Report Update</p>
              <p className="font-semibold text-white">{formatDateTime(data.last_updated_at)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Three Primary Report Cards */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {[
          {
            title: "Pole Survey Report",
            count: data.available_pole_survey_count,
            desc: "Field pole survey workbooks organized by region and zone.",
            icon: ClipboardList,
            path: "/pole-survey",
          },
          {
            title: "Lamp Installation Report",
            count: data.available_lamp_installation_count,
            desc: "Installed lamp records and zone asset templates.",
            icon: Lightbulb,
            path: "/lamp-installation",
          },
          {
            title: "Merged Report",
            count: data.available_merged_count,
            desc: "Published reconciled LED reports ready for Excel preview and download.",
            icon: GitMerge,
            path: "/merged-reports",
          },
        ].map((card) => (
          <div
            key={card.title}
            onClick={() => navigate(card.path)}
            className="group cursor-pointer rounded-xl border border-slate-200/80 bg-white p-5 shadow-card transition-all hover:-translate-y-0.5 hover:border-[#18A6A0] hover:shadow-md"
          >
            <div className="flex items-center justify-between">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#075D6B]/10 text-[#075D6B]">
                <card.icon className="h-5 w-5" />
              </div>
              <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-[#075D6B]">
                {card.count} Available
              </span>
            </div>
            <h2 className="mt-4 text-base font-bold text-[#173042]">{card.title}</h2>
            <p className="mt-1 text-xs leading-relaxed text-[#718096]">{card.desc}</p>
            <div className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-[#0D7780] group-hover:translate-x-0.5 transition">
              Open Reports <ArrowRight className="h-3.5 w-3.5" />
            </div>
          </div>
        ))}
      </div>

      {/* Hierarchy + Availability + Recent Reports */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <HierarchyExplorer onZoneSelected={() => navigate("/merged-reports")} />
        </div>

        <div className="lg:col-span-8 space-y-6">
          {/* Regional Availability */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-sm font-bold text-[#173042]">Region-Wise Report Availability</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50 text-[#718096]">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Region</th>
                    <th className="px-4 py-2.5 font-semibold text-center">Zones</th>
                    <th className="px-4 py-2.5 font-semibold text-center">Pole Survey</th>
                    <th className="px-4 py-2.5 font-semibold text-center">Lamp Install</th>
                    <th className="px-4 py-2.5 font-semibold text-center">Published Merged</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.region_availability.map((r) => (
                    <tr key={r.region_id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3 font-semibold text-[#173042]">{r.region_name}</td>
                      <td className="px-4 py-3 text-center">{r.total_zones}</td>
                      <td className="px-4 py-3 text-center font-semibold text-emerald-700">
                        {r.pole_survey_count}
                      </td>
                      <td className="px-4 py-3 text-center font-semibold text-sky-700">
                        {r.lamp_installation_count}
                      </td>
                      <td className="px-4 py-3 text-center font-semibold text-[#075D6B]">
                        {r.merged_published_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Recently Updated Reports */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-sm font-bold text-[#173042]">Recently Updated Reports</h2>
            </div>
            {data.recent_available_reports.length === 0 ? (
              <p className="p-6 text-center text-xs text-[#718096]">
                No reports have been published for your account yet.
              </p>
            ) : (
              <div className="divide-y divide-slate-100">
                {data.recent_available_reports.map((item, idx) => (
                  <div
                    key={`${item.category}-${item.id}-${idx}`}
                    onClick={() =>
                      navigate(
                        item.category === "pole_survey"
                          ? "/pole-survey"
                          : item.category === "lamp_installation"
                          ? "/lamp-installation"
                          : "/merged-reports"
                      )
                    }
                    className="flex cursor-pointer items-center justify-between gap-3 px-5 py-3 hover:bg-teal-50/40"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <MapPin className="h-4 w-4 text-[#18A6A0] shrink-0" />
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-[#173042]">
                          {item.title}
                        </p>
                        <p className="text-[11px] text-[#718096]">
                          {formatReportType(item.category)} • {item.region_name} / {item.zone_name}{" "}
                          • v{item.version}
                        </p>
                      </div>
                    </div>
                    <span className="shrink-0 text-[11px] text-[#718096]">
                      {formatDateTime(item.updated_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

