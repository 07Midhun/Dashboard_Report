import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Building2,
  ClipboardList,
  GitMerge,
  Lightbulb,
  Map,
  MapPin,
  PlusCircle,
  RefreshCw,
  Upload,
} from "lucide-react";
import { dashboardApi } from "../../services/endpoints";
import { extractErrorMessage } from "../../services/api";
import type { AdminDashboardData } from "../../types";
import { formatDateTime, formatReportType } from "../../utils/format";
import { StatCard } from "../../components/common/StatCard";
import { StatusBadge } from "../../components/common/StatusBadge";

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await dashboardApi.getAdmin();
      setData(res);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-[#718096]">
        Loading administrator dashboard metrics...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
        {error || "Unable to load dashboard data."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#173042]">Administrator Dashboard</h1>
          <p className="mt-1 text-sm text-[#718096]">
            Live overview of customers, regions, zones, report uploads, and LED reconciliation runs.
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-[#173042] shadow-sm hover:bg-slate-50"
        >
          <RefreshCw className="h-3.5 w-3.5 text-[#075D6B]" />
          Refresh Metrics
        </button>
      </div>

      {/* 6 Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          title="Total Customers"
          value={data.total_customers}
          subtitle="Active municipal & utility accounts"
          icon={Building2}
          onClick={() => navigate("/admin/customers")}
        />
        <StatCard
          title="Total Regions"
          value={data.total_regions}
          subtitle="Configured administrative regions"
          icon={Map}
          accent="mid"
          onClick={() => navigate("/admin/regions")}
        />
        <StatCard
          title="Total Zones"
          value={data.total_zones}
          subtitle="Independent reporting zones"
          icon={MapPin}
          accent="bright"
          onClick={() => navigate("/admin/zones")}
        />
        <StatCard
          title="Pole Survey Reports"
          value={data.total_pole_survey_reports}
          subtitle="Active uploaded survey workbooks"
          icon={ClipboardList}
          onClick={() => navigate("/pole-survey")}
        />
        <StatCard
          title="Lamp Installation Reports"
          value={data.total_lamp_installation_reports}
          subtitle="Master formatting templates uploaded"
          icon={Lightbulb}
          accent="mid"
          onClick={() => navigate("/lamp-installation")}
        />
        <StatCard
          title="Merged Reports"
          value={data.total_merged_reports}
          subtitle="Generated zone reconciliations"
          icon={GitMerge}
          accent="bright"
          onClick={() => navigate("/merged-reports")}
        />
      </div>

      {/* Quick Actions */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#718096]">Quick Actions</h2>
        <div className="mt-3.5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "Upload Pole Survey", icon: Upload, path: "/pole-survey", primary: true },
            { label: "Upload Lamp Report", icon: Upload, path: "/lamp-installation", primary: true },
            { label: "Generate Merged", icon: GitMerge, path: "/merged-reports", primary: true },
            { label: "Manage Customers", icon: PlusCircle, path: "/admin/customers", primary: false },
            { label: "Manage Regions", icon: Map, path: "/admin/regions", primary: false },
            { label: "Manage Zones", icon: MapPin, path: "/admin/zones", primary: false },
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
              <p className="p-6 text-center text-xs text-[#718096]">No reports uploaded yet.</p>
            ) : (
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50 text-[#718096]">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Report</th>
                    <th className="px-4 py-2.5 font-semibold">Location</th>
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
                        {u.region_name} / <span className="font-medium">{u.zone_name}</span>
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
                No Merged Reports generated yet.
              </p>
            ) : (
              <table className="min-w-full text-left text-xs">
                <thead className="bg-slate-50 text-[#718096]">
                  <tr>
                    <th className="px-4 py-2.5 font-semibold">Zone</th>
                    <th className="px-4 py-2.5 font-semibold">Added LEDs</th>
                    <th className="px-4 py-2.5 font-semibold">Status</th>
                    <th className="px-4 py-2.5 font-semibold">Generated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.recent_merged_reports.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50/70">
                      <td className="px-4 py-3">
                        <p className="font-semibold text-[#173042]">{m.zone_name}</p>
                        <p className="text-[11px] text-[#718096]">
                          {m.customer_name} • {m.region_name}
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

      {/* Report Availability by Region + Processing Activity */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="text-sm font-bold text-[#173042]">Report Availability by Region</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[#718096]">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Customer / Region</th>
                  <th className="px-4 py-2.5 font-semibold text-center">Zones</th>
                  <th className="px-4 py-2.5 font-semibold text-center">Pole Survey</th>
                  <th className="px-4 py-2.5 font-semibold text-center">Lamp Install</th>
                  <th className="px-4 py-2.5 font-semibold text-center">Published</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.report_availability_by_region.map((r) => (
                  <tr key={r.region_id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-[#173042]">{r.region_name}</p>
                      <p className="text-[11px] text-[#718096]">{r.customer_name}</p>
                    </td>
                    <td className="px-4 py-3 text-center font-semibold">{r.total_zones}</td>
                    <td className="px-4 py-3 text-center text-emerald-700 font-semibold">
                      {r.pole_survey_count}/{r.total_zones}
                    </td>
                    <td className="px-4 py-3 text-center text-sky-700 font-semibold">
                      {r.lamp_installation_count}/{r.total_zones}
                    </td>
                    <td className="px-4 py-3 text-center text-[#075D6B] font-semibold">
                      {r.merged_published_count}/{r.total_zones}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Latest Processing & Failed Records */}
        <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
          <div className="border-b border-slate-100 px-5 py-4 flex items-center justify-between">
            <h2 className="text-sm font-bold text-[#173042]">Latest Processing Activity</h2>
            {data.failed_processing_records.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-200">
                <AlertTriangle className="h-3 w-3" />
                {data.failed_processing_records.length} failed
              </span>
            )}
          </div>
          <div className="divide-y divide-slate-100">
            {data.latest_processing_activity.length === 0 ? (
              <p className="p-6 text-center text-xs text-[#718096]">
                No processing runs recorded yet.
              </p>
            ) : (
              data.latest_processing_activity.map((log) => (
                <div key={log.id} className="flex items-start justify-between gap-3 px-5 py-3 text-xs">
                  <div>
                    <p className="font-semibold text-[#173042]">
                      {log.region_name} — {log.zone_name}
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
    </div>
  );
}

