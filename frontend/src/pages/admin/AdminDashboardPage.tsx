import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Building2,
  ClipboardList,
  Clock,
  Filter,
  GitMerge,
  Layers,
  Lightbulb,
  Map,
  MapPin,
  PlusCircle,
  RefreshCw,
  RotateCcw,
  Upload,
} from "lucide-react";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { dashboardApi } from "../../services/endpoints";
import { extractErrorMessage } from "../../services/api";
import type { AdminDashboardData } from "../../types";
import { formatDateTime, formatReportType } from "../../utils/format";
import { StatCard } from "../../components/common/StatCard";
import { StatusBadge } from "../../components/common/StatusBadge";

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const { tree } = useHierarchy();

  const [customerFilter, setCustomerFilter] = useState<number | "">("");
  const [regionFilter, setRegionFilter] = useState<number | "">("");
  const [zoneFilter, setZoneFilter] = useState<number | "">("");
  const [availabilityView, setAvailabilityView] = useState<"region" | "zone">("region");

  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await dashboardApi.getAdmin({
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
    loadData();
  }, [loadData]);

  // Cascading dropdown options from tree
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

  const handleCustomerChange = (val: string) => {
    const nextCust = val ? Number(val) : "";
    setCustomerFilter(nextCust);
    setRegionFilter("");
    setZoneFilter("");
  };

  const handleRegionChange = (val: string) => {
    const nextReg = val ? Number(val) : "";
    setRegionFilter(nextReg);
    setZoneFilter("");
  };

  const resetFilters = () => {
    setCustomerFilter("");
    setRegionFilter("");
    setZoneFilter("");
  };

  const hasFilters = customerFilter !== "" || regionFilter !== "" || zoneFilter !== "";

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#173042]">Administrator Dashboard</h1>
          <p className="mt-1 text-sm text-[#718096]">
            Ward-wise operational overview of Pole Surveys, Lamp Installations, and LED reconciliation runs.
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-[#173042] shadow-sm hover:bg-slate-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 text-[#075D6B] ${loading ? "animate-spin" : ""}`} />
          Refresh Metrics
        </button>
      </div>

      {/* Customer / Region / Zone Filter Bar */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-card flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#075D6B] mr-1">
          <Filter className="h-3.5 w-3.5" />
          Scope Filters
        </div>

        <select
          aria-label="Filter by customer"
          value={customerFilter}
          onChange={(e) => handleCustomerChange(e.target.value)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-[#173042] focus:border-[#18A6A0] focus:bg-white focus:outline-none"
        >
          <option value="">All Customers</option>
          {tree.map((c) => (
            <option key={c.id} value={c.id}>
              {c.customer_name}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by region"
          value={regionFilter}
          onChange={(e) => handleRegionChange(e.target.value)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-[#173042] focus:border-[#18A6A0] focus:bg-white focus:outline-none"
        >
          <option value="">All Regions</option>
          {regionOptions.map((r) => (
            <option key={r.id} value={r.id}>
              {customerFilter === "" ? `${r.customerName} — ${r.region_name}` : r.region_name}
            </option>
          ))}
        </select>

        <select
          aria-label="Filter by zone"
          value={zoneFilter}
          onChange={(e) => setZoneFilter(e.target.value ? Number(e.target.value) : "")}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-[#173042] focus:border-[#18A6A0] focus:bg-white focus:outline-none"
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
            onClick={resetFilters}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-[#718096] hover:bg-slate-100 hover:text-[#173042]"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        )}

        {data && (
          <div className="ml-auto flex flex-wrap items-center gap-3 text-xs text-[#718096]">
            <span>
              <strong className="text-[#173042]">{data.total_customers}</strong> Customers
            </span>
            <span>•</span>
            <span>
              <strong className="text-[#173042]">{data.total_regions}</strong> Regions
            </span>
            <span>•</span>
            <span>
              <strong className="text-[#173042]">{data.total_zones}</strong> Zones
            </span>
          </div>
        )}
      </div>

      {loading && !data ? (
        <div className="flex h-64 items-center justify-center text-sm text-[#718096]">
          Loading administrator dashboard metrics...
        </div>
      ) : error || !data ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
          {error || "Unable to load dashboard data."}
        </div>
      ) : (
        <>
          {/* 6 Ward-Level Summary Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard
              title="Total Wards"
              value={data.total_wards}
              subtitle={`Across ${data.total_zones} zone(s) in ${data.total_regions} region(s)`}
              icon={Layers}
              onClick={() => navigate("/admin/wards")}
            />
            <StatCard
              title="Wards w/ Pole Survey"
              value={data.wards_with_pole_survey}
              subtitle="Wards with active Pole Survey upload"
              icon={ClipboardList}
              accent="mid"
              onClick={() => navigate("/pole-survey")}
            />
            <StatCard
              title="Wards w/ Lamp Installation"
              value={data.wards_with_lamp_installation}
              subtitle="Wards with master Lamp Install workbook"
              icon={Lightbulb}
              accent="bright"
              onClick={() => navigate("/lamp-installation")}
            />
            <StatCard
              title="Wards w/ Completed Merged"
              value={data.wards_with_completed_merged}
              subtitle={`${data.wards_with_published_merged} published to customer portal`}
              icon={GitMerge}
              onClick={() => navigate("/merged-reports")}
            />
            <StatCard
              title="Wards Awaiting Uploads"
              value={data.wards_awaiting_uploads}
              subtitle="Active wards missing one or both source files"
              icon={Clock}
              accent="slate"
              onClick={() => navigate("/pole-survey")}
            />
            <StatCard
              title="Wards w/ Processing Errors"
              value={data.wards_with_processing_errors}
              subtitle="Wards whose latest merge run failed"
              icon={AlertTriangle}
              accent="slate"
              onClick={() => navigate("/merged-reports")}
            />
          </div>

          {/* Quick Actions */}
          <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card">
            <h2 className="text-sm font-bold uppercase tracking-wider text-[#718096]">
              Quick Actions
            </h2>
            <div className="mt-3.5 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
              {[
                { label: "Upload Pole Survey", icon: Upload, path: "/pole-survey", primary: true },
                {
                  label: "Upload Lamp Report",
                  icon: Upload,
                  path: "/lamp-installation",
                  primary: true,
                },
                { label: "Generate Merged", icon: GitMerge, path: "/merged-reports", primary: true },
                {
                  label: "Manage Customers",
                  icon: PlusCircle,
                  path: "/admin/customers",
                  primary: false,
                },
                { label: "Manage Regions", icon: Map, path: "/admin/regions", primary: false },
                { label: "Manage Zones", icon: MapPin, path: "/admin/zones", primary: false },
                { label: "Manage Wards", icon: Layers, path: "/admin/wards", primary: false },
              ].map((btn) => (
                <button
                  key={btn.label}
                  type="button"
                  onClick={() => navigate(btn.path)}
                  className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-xs font-semibold transition ${
                    btn.primary
                      ? "bg-[#075D6B] text-white hover:bg-[#0D7780] shadow-sm"
                      : "border border-slate-200 bg-slate-50 text-[#173042] hover:border-[#18A6A0] hover:bg-teal-50/40"
                  }`}
                >
                  <btn.icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{btn.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Recent Uploads & Recent Merged Reports */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            {/* Recent Uploads */}
            <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <h2 className="text-sm font-bold text-[#173042]">Recent Uploads</h2>
                <button
                  type="button"
                  onClick={() => navigate("/admin/upload-history")}
                  className="text-xs font-semibold text-[#0D7780] hover:underline"
                >
                  View History
                </button>
              </div>
              <div className="overflow-x-auto">
                {data.recent_uploads.length === 0 ? (
                  <p className="p-6 text-center text-xs text-[#718096]">
                    No reports uploaded for current filter.
                  </p>
                ) : (
                  <table className="min-w-full text-left text-xs">
                    <thead className="bg-slate-50 text-[#718096]">
                      <tr>
                        <th className="px-4 py-2.5 font-semibold">Report</th>
                        <th className="px-4 py-2.5 font-semibold">Ward / Zone</th>
                        <th className="px-4 py-2.5 font-semibold">Ver</th>
                        <th className="px-4 py-2.5 font-semibold">Uploaded</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.recent_uploads.map((u) => (
                        <tr key={u.id} className="hover:bg-slate-50/70">
                          <td className="px-4 py-3">
                            <p className="font-semibold text-[#173042]">{u.original_filename}</p>
                            <p className="text-[11px] text-[#718096]">
                              {formatReportType(u.report_type)}
                            </p>
                          </td>
                          <td className="px-4 py-3 text-[#173042]">
                            <p className="font-semibold">
                              <span className="mr-1 rounded bg-[#075D6B]/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#075D6B]">
                                {u.ward_number}
                              </span>
                              {u.ward_name}
                            </p>
                            <p className="text-[11px] text-[#718096]">
                              {u.region_name} / {u.zone_name}
                            </p>
                          </td>
                          <td className="px-4 py-3 font-mono font-semibold text-[#075D6B]">
                            v{u.version}
                          </td>
                          <td className="px-4 py-3 text-[#718096]">
                            {formatDateTime(u.uploaded_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Recent Merged Reports */}
            <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <h2 className="text-sm font-bold text-[#173042]">Recent Merged Reports</h2>
                <button
                  type="button"
                  onClick={() => navigate("/merged-reports")}
                  className="text-xs font-semibold text-[#0D7780] hover:underline"
                >
                  Open Workspace
                </button>
              </div>
              <div className="overflow-x-auto">
                {data.recent_merged_reports.length === 0 ? (
                  <p className="p-6 text-center text-xs text-[#718096]">
                    No Merged Reports generated for current filter.
                  </p>
                ) : (
                  <table className="min-w-full text-left text-xs">
                    <thead className="bg-slate-50 text-[#718096]">
                      <tr>
                        <th className="px-4 py-2.5 font-semibold">Ward / Zone</th>
                        <th className="px-4 py-2.5 font-semibold">Added LEDs</th>
                        <th className="px-4 py-2.5 font-semibold">Status</th>
                        <th className="px-4 py-2.5 font-semibold">Generated</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.recent_merged_reports.map((m) => (
                        <tr key={m.id} className="hover:bg-slate-50/70">
                          <td className="px-4 py-3">
                            <p className="font-semibold text-[#173042]">
                              <span className="mr-1 rounded bg-[#075D6B]/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#075D6B]">
                                {m.ward_number}
                              </span>
                              {m.ward_name}
                            </p>
                            <p className="text-[11px] text-[#718096]">
                              {m.customer_name} • {m.region_name} • {m.zone_name}
                            </p>
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-bold text-[#075D6B]">+{m.added_records}</span>
                            <span className="text-[#718096]"> / {m.final_merged_records} total</span>
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={m.status} />
                          </td>
                          <td className="px-4 py-3 text-[#718096]">
                            {formatDateTime(m.generated_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          {/* Ward Availability Breakdown + Processing Activity */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
              <div className="border-b border-slate-100 px-5 py-4 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-bold text-[#173042]">
                  Ward Report Availability
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
                        <th className="px-4 py-2.5 font-semibold">Customer / Region</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Zones</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Wards</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Pole Survey</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Lamp Install</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Published</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Awaiting</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.report_availability_by_region.map((r) => (
                        <tr key={r.region_id} className="hover:bg-slate-50/70">
                          <td className="px-4 py-3">
                            <p className="font-semibold text-[#173042]">{r.region_name}</p>
                            <p className="text-[11px] text-[#718096]">{r.customer_name}</p>
                          </td>
                          <td className="px-3 py-3 text-center font-semibold">{r.total_zones}</td>
                          <td className="px-3 py-3 text-center font-bold text-[#173042]">
                            {r.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-emerald-700 font-semibold">
                            {r.pole_survey_count}/{r.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-sky-700 font-semibold">
                            {r.lamp_installation_count}/{r.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-[#075D6B] font-semibold">
                            {r.merged_published_count}/{r.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-amber-700 font-semibold">
                            {r.awaiting_uploads_count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <table className="min-w-full text-left text-xs">
                    <thead className="sticky top-0 bg-slate-50 text-[#718096]">
                      <tr>
                        <th className="px-4 py-2.5 font-semibold">Zone / Region</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Wards</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Pole Survey</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Lamp Install</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Published</th>
                        <th className="px-3 py-2.5 font-semibold text-center">Awaiting</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.zone_availability.map((z) => (
                        <tr key={z.zone_id} className="hover:bg-slate-50/70">
                          <td className="px-4 py-3">
                            <p className="font-semibold text-[#173042]">
                              {z.zone_name}{" "}
                              {z.zone_code ? (
                                <span className="font-mono text-[10px] text-[#075D6B]">
                                  ({z.zone_code})
                                </span>
                              ) : null}
                            </p>
                            <p className="text-[11px] text-[#718096]">
                              {z.customer_name} • {z.region_name}
                            </p>
                          </td>
                          <td className="px-3 py-3 text-center font-bold text-[#173042]">
                            {z.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-emerald-700 font-semibold">
                            {z.pole_survey_count}/{z.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-sky-700 font-semibold">
                            {z.lamp_installation_count}/{z.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-[#075D6B] font-semibold">
                            {z.merged_published_count}/{z.total_wards}
                          </td>
                          <td className="px-3 py-3 text-center text-amber-700 font-semibold">
                            {z.awaiting_uploads_count}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Latest Processing & Failed Records */}
            <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
              <div className="border-b border-slate-100 px-5 py-4 flex items-center justify-between">
                <h2 className="text-sm font-bold text-[#173042]">Latest Processing Activity</h2>
                {data.wards_with_processing_errors > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-200">
                    <AlertTriangle className="h-3 w-3" />
                    {data.wards_with_processing_errors} ward(s) with errors
                  </span>
                )}
              </div>
              <div className="divide-y divide-slate-100">
                {data.latest_processing_activity.length === 0 ? (
                  <p className="p-6 text-center text-xs text-[#718096]">
                    No processing runs recorded yet for current filter.
                  </p>
                ) : (
                  data.latest_processing_activity.map((log) => (
                    <div
                      key={log.id}
                      className="flex items-start justify-between gap-3 px-5 py-3 text-xs"
                    >
                      <div>
                        <p className="font-semibold text-[#173042]">
                          <span className="mr-1.5 rounded bg-[#075D6B]/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#075D6B]">
                            {log.ward_number}
                          </span>
                          {log.ward_name} • {log.zone_name}{" "}
                          <span className="font-normal text-[#718096]">({log.region_name})</span>
                        </p>
                        {log.error_message ? (
                          <p className="mt-0.5 text-rose-600">{log.error_message}</p>
                        ) : (
                          <p className="mt-0.5 text-[#718096]">
                            Added: <strong>{log.added_records}</strong> • Duplicates:{" "}
                            <strong>{log.duplicate_records}</strong> • Invalid:{" "}
                            <strong>{log.invalid_records}</strong> • Unknown:{" "}
                            <strong>{log.unknown_lamp_type_records}</strong>
                          </p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <StatusBadge status={log.processing_status} />
                        <p className="mt-1 text-[11px] text-[#718096]">
                          {formatDateTime(log.created_at)}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
