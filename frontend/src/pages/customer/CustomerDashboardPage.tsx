import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ClipboardList,
  Clock,
  Filter,
  GitMerge,
  Layers,
  Lightbulb,
  MapPin,
  RotateCcw,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { extractErrorMessage } from "../../services/api";
import { dashboardApi } from "../../services/endpoints";
import type { CustomerDashboardData } from "../../types";
import { formatDateTime, formatReportType } from "../../utils/format";
import { HierarchyExplorer } from "../../components/hierarchy/HierarchyExplorer";

export function CustomerDashboardPage() {
  const { user } = useAuth();
  const { tree } = useHierarchy();
  const navigate = useNavigate();

  const [customerFilter, setCustomerFilter] = useState<number | "">("");
  const [regionFilter, setRegionFilter] = useState<number | "">("");
  const [zoneFilter, setZoneFilter] = useState<number | "">("");
  const [availabilityView, setAvailabilityView] = useState<"region" | "zone">("region");

  const [data, setData] = useState<CustomerDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await dashboardApi.getCustomer({
        customer_id: customerFilter === "" ? undefined : customerFilter,
        region_id: regionFilter === "" ? undefined : regionFilter,
        zone_id: zoneFilter === "" ? undefined : zoneFilter,
      });
      setData(res);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [customerFilter, regionFilter, zoneFilter]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const regionOptions = tree.flatMap((c) =>
    customerFilter === "" || c.id === customerFilter
      ? c.regions.map((r) => ({ ...r, customerName: c.customer_name }))
      : []
  );
  const zoneOptions = regionOptions.flatMap((r) =>
    regionFilter === "" || r.id === regionFilter
      ? r.zones.map((z) => ({ ...z, regionName: r.region_name }))
      : []
  );

  const hasFilters = customerFilter !== "" || regionFilter !== "" || zoneFilter !== "";

  if (loading && !data) {
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
              • {data.total_regions} Regions • {data.total_zones} Zones • {data.total_wards} Wards
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

      {/* Customer / Region / Zone Filter Bar */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-card flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#075D6B] mr-1">
          <Filter className="h-3.5 w-3.5" />
          Filter Scope
        </div>

        {tree.length > 1 && (
          <select
            aria-label="Filter by customer"
            value={customerFilter}
            onChange={(e) => {
              setCustomerFilter(e.target.value ? Number(e.target.value) : "");
              setRegionFilter("");
              setZoneFilter("");
            }}
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-[#173042]"
          >
            <option value="">All Assigned Customers</option>
            {tree.map((c) => (
              <option key={c.id} value={c.id}>
                {c.customer_name}
              </option>
            ))}
          </select>
        )}

        <select
          aria-label="Filter by region"
          value={regionFilter}
          onChange={(e) => {
            setRegionFilter(e.target.value ? Number(e.target.value) : "");
            setZoneFilter("");
          }}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-[#173042]"
        >
          <option value="">All Regions</option>
          {regionOptions.map((r) => (
            <option key={r.id} value={r.id}>
              {r.region_name}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by zone"
          value={zoneFilter}
          onChange={(e) => setZoneFilter(e.target.value ? Number(e.target.value) : "")}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-[#173042]"
        >
          <option value="">All Zones</option>
          {zoneOptions.map((z) => (
            <option key={z.id} value={z.id}>
              {z.zone_name} {z.zone_code ? `(${z.zone_code})` : ""}
            </option>
          ))}
        </select>

        {hasFilters && (
          <button
            type="button"
            onClick={() => {
              setCustomerFilter("");
              setRegionFilter("");
              setZoneFilter("");
            }}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-[#718096] hover:bg-slate-100"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        )}

        <div className="ml-auto flex flex-wrap items-center gap-3 text-xs text-[#718096]">
          <span className="inline-flex items-center gap-1">
            <Layers className="h-3.5 w-3.5 text-[#075D6B]" />
            <strong className="text-[#173042]">{data.total_wards}</strong> Total Wards
          </span>
          <span>•</span>
          <span>
            <strong className="text-amber-700">{data.wards_awaiting_uploads}</strong> Awaiting Uploads
          </span>
        </div>
      </div>

      {/* Three Primary Report Cards */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {[
          {
            title: "Pole Survey Report",
            count: `${data.wards_with_pole_survey}/${data.total_wards} Wards`,
            desc: "Field pole survey workbooks organized by region, zone, and ward.",
            icon: ClipboardList,
            path: "/pole-survey",
          },
          {
            title: "Lamp Installation Report",
            count: `${data.wards_with_lamp_installation}/${data.total_wards} Wards`,
            desc: "Installed lamp records and ward asset formatting templates.",
            icon: Lightbulb,
            path: "/lamp-installation",
          },
          {
            title: "Merged Report",
            count: `${data.wards_with_completed_merged}/${data.total_wards} Published`,
            desc: "Published reconciled LED reports ready for ward Excel preview and download.",
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
                {card.count}
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
          <HierarchyExplorer onWardSelected={() => navigate("/merged-reports")} />
        </div>

        <div className="lg:col-span-8 space-y-6">
          {/* Ward Report Availability (By Region / By Zone) */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold text-[#173042]">
                Ward-Wise Report Availability
              </h2>
              <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-[11px] font-semibold">
                <button
                  type="button"
                  onClick={() => setAvailabilityView("region")}
                  className={`rounded-md px-2.5 py-1 transition ${
                    availabilityView === "region"
                      ? "bg-[#075D6B] text-white"
                      : "text-[#718096] hover:text-[#173042]"
                  }`}
                >
                  By Region
                </button>
                <button
                  type="button"
                  onClick={() => setAvailabilityView("zone")}
                  className={`rounded-md px-2.5 py-1 transition ${
                    availabilityView === "zone"
                      ? "bg-[#075D6B] text-white"
                      : "text-[#718096] hover:text-[#173042]"
                  }`}
                >
                  By Zone
                </button>
              </div>
            </div>
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              {availabilityView === "region" ? (
                <table className="min-w-full text-left text-xs">
                  <thead className="sticky top-0 bg-slate-50 text-[#718096]">
                    <tr>
                      <th className="px-4 py-2.5 font-semibold">Region</th>
                      <th className="px-4 py-2.5 font-semibold text-center">Zones</th>
                      <th className="px-4 py-2.5 font-semibold text-center">Wards</th>
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
                        <td className="px-4 py-3 text-center font-bold">{r.total_wards}</td>
                        <td className="px-4 py-3 text-center font-semibold text-emerald-700">
                          {r.pole_survey_count}/{r.total_wards}
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-sky-700">
                          {r.lamp_installation_count}/{r.total_wards}
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-[#075D6B]">
                          {r.merged_published_count}/{r.total_wards}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table className="min-w-full text-left text-xs">
                  <thead className="sticky top-0 bg-slate-50 text-[#718096]">
                    <tr>
                      <th className="px-4 py-2.5 font-semibold">Zone</th>
                      <th className="px-4 py-2.5 font-semibold">Region</th>
                      <th className="px-4 py-2.5 font-semibold text-center">Wards</th>
                      <th className="px-4 py-2.5 font-semibold text-center">Pole Survey</th>
                      <th className="px-4 py-2.5 font-semibold text-center">Lamp Install</th>
                      <th className="px-4 py-2.5 font-semibold text-center">Published Merged</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.zone_availability.map((z) => (
                      <tr key={z.zone_id} className="hover:bg-slate-50/70">
                        <td className="px-4 py-3 font-semibold text-[#173042]">
                          {z.zone_name}{" "}
                          {z.zone_code ? (
                            <span className="font-mono text-[10px] text-[#075D6B]">
                              ({z.zone_code})
                            </span>
                          ) : null}
                        </td>
                        <td className="px-4 py-3 text-[#718096]">{z.region_name}</td>
                        <td className="px-4 py-3 text-center font-bold">{z.total_wards}</td>
                        <td className="px-4 py-3 text-center font-semibold text-emerald-700">
                          {z.pole_survey_count}/{z.total_wards}
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-sky-700">
                          {z.lamp_installation_count}/{z.total_wards}
                        </td>
                        <td className="px-4 py-3 text-center font-semibold text-[#075D6B]">
                          {z.merged_published_count}/{z.total_wards}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* Recently Updated Reports */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-sm font-bold text-[#173042]">Recently Updated Reports</h2>
            </div>
            {data.recent_available_reports.length === 0 ? (
              <p className="p-6 text-center text-xs text-[#718096]">
                No reports have been published for your selection yet.
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
                          {formatReportType(item.category)} • {item.ward_number} ({item.ward_name}) •{" "}
                          {item.region_name} / {item.zone_name} • v{item.version}
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

