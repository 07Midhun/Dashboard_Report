import { useCallback, useEffect, useState } from "react";
import {
  Download,
  Eye,
  FileSpreadsheet,
  History,
  Trash2,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { reportFilesApi } from "../../services/endpoints";
import type { ReportFile, ReportType } from "../../types";
import { formatBytes, formatDateTime } from "../../utils/format";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { HierarchyExplorer } from "../../components/hierarchy/HierarchyExplorer";
import { ExcelPreviewModal } from "../../components/reports/ExcelPreviewModal";
import { ReportUploadPanel } from "../../components/reports/ReportUploadPanel";

export function SourceReportPage({ reportType }: { reportType: ReportType }) {
  const { user } = useAuth();
  const { selection, selectedCustomer, selectedRegion, selectedZone, refreshTree } = useHierarchy();
  const { showToast } = useToast();

  const isAdmin = user?.role === "admin";
  const title = reportType === "pole_survey" ? "Pole Survey Report" : "Lamp Installation Report";

  const [reports, setReports] = useState<ReportFile[]>([]);
  const [loading, setLoading] = useState(false);

  const [previewTarget, setPreviewTarget] = useState<{ id: number; version?: number } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ReportFile | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadReports = useCallback(async () => {
    setLoading(true);
    try {
      const data = await reportFilesApi.list(reportType, {
        customer_id: selection.customerId ?? undefined,
      });
      setReports(data);
    } catch (err) {
      showToast("error", "Failed to load reports", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [reportType, selection.customerId, showToast]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const activeZoneReport =
    selection.zoneId != null
      ? reports.find((r) => r.zone_id === selection.zoneId) ?? null
      : null;

  const filteredReports = reports.filter((r) => {
    if (selection.zoneId) return r.zone_id === selection.zoneId;
    if (selection.regionId) return r.region_id === selection.regionId;
    return true;
  });

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await reportFilesApi.remove(reportType, deleteTarget.id);
      showToast("success", "Report Deleted", `${deleteTarget.original_filename} removed.`);
      setDeleteTarget(null);
      await Promise.all([loadReports(), refreshTree()]);
    } catch (err) {
      showToast("error", "Delete Failed", extractErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">{title}s</h1>
        <p className="mt-1 text-sm text-[#718096]">
          {isAdmin
            ? `Upload, replace, preview, and manage zone-wise ${title} workbooks.`
            : `Browse, search, preview, and download authorized ${title} workbooks.`}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Region / Zone Hierarchy */}
        <div className="lg:col-span-4">
          <HierarchyExplorer />
        </div>

        {/* Right Workspace */}
        <div className="lg:col-span-8 space-y-6">
          {/* Admin Upload Panel */}
          {isAdmin && (
            selectedCustomer && selectedRegion && selectedZone ? (
              <ReportUploadPanel
                reportType={reportType}
                customerId={selectedCustomer.id}
                regionId={selectedRegion.id}
                zoneId={selectedZone.id}
                zoneName={selectedZone.zone_name}
                existingReport={activeZoneReport}
                onUploaded={async () => {
                  await Promise.all([loadReports(), refreshTree()]);
                }}
              />
            ) : (
              <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-[#718096]">
                Select a <strong className="text-[#075D6B]">Zone</strong> from the hierarchy on the
                left to upload or replace its {title}.
              </div>
            )
          )}

          {/* Selected Zone Active Report Card */}
          {selectedZone && activeZoneReport && (
            <div className="rounded-xl border border-teal-200 bg-white p-5 shadow-card">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#075D6B]/10 text-[#075D6B] shrink-0">
                    <FileSpreadsheet className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-[#173042]">
                        {activeZoneReport.original_filename}
                      </h3>
                      <span className="rounded-full bg-teal-50 border border-teal-200 px-2 py-0.5 text-[11px] font-bold text-[#075D6B]">
                        v{activeZoneReport.version}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[#718096]">
                      Sheet: <strong>{activeZoneReport.sheet_name}</strong> •{" "}
                      <strong>{activeZoneReport.row_count}</strong> rows •{" "}
                      {formatBytes(activeZoneReport.file_size)} • Updated{" "}
                      {formatDateTime(activeZoneReport.uploaded_at)}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPreviewTarget({ id: activeZoneReport.id })}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#173042] hover:bg-slate-50"
                  >
                    <Eye className="h-3.5 w-3.5 text-[#0D7780]" />
                    Preview
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      reportFilesApi.download(
                        reportType,
                        activeZoneReport.id,
                        activeZoneReport.original_filename
                      )
                    }
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#075D6B] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#0D7780]"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download
                  </button>
                  {isAdmin && (
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(activeZoneReport)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  )}
                </div>
              </div>

              {/* Version History (Admin) */}
              {isAdmin && activeZoneReport.versions.length > 0 && (
                <div className="mt-4 border-t border-slate-100 pt-3">
                  <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#718096]">
                    <History className="h-3.5 w-3.5" /> Version History
                  </p>
                  <div className="space-y-1.5">
                    {activeZoneReport.versions.map((ver) => (
                      <div
                        key={ver.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-[#075D6B]">v{ver.version}</span>
                          <span className="font-medium text-[#173042]">{ver.original_filename}</span>
                          <span className="text-[#718096]">
                            ({ver.row_count} rows • {formatBytes(ver.file_size)})
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-[11px] text-[#718096]">
                            {ver.uploaded_by_name} • {formatDateTime(ver.uploaded_at)}
                          </span>
                          <button
                            type="button"
                            onClick={() =>
                              setPreviewTarget({ id: activeZoneReport.id, version: ver.version })
                            }
                            className="text-xs font-semibold text-[#0D7780] hover:underline"
                          >
                            Preview
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              reportFilesApi.download(
                                reportType,
                                activeZoneReport.id,
                                ver.original_filename,
                                ver.version
                              )
                            }
                            className="text-xs font-semibold text-[#075D6B] hover:underline"
                          >
                            Download
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* List of Reports for selected Customer / Region / Zone */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-4 flex items-center justify-between">
              <h2 className="text-sm font-bold text-[#173042]">
                Available {title}s ({filteredReports.length})
              </h2>
            </div>

            {loading ? (
              <p className="p-6 text-center text-xs text-[#718096]">Loading reports...</p>
            ) : filteredReports.length === 0 ? (
              <p className="p-8 text-center text-xs text-[#718096]">
                No {title} workbooks found for the current filter.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[#718096]">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Region / Zone</th>
                      <th className="px-4 py-3 font-semibold">Workbook</th>
                      <th className="px-4 py-3 font-semibold">Rows</th>
                      <th className="px-4 py-3 font-semibold">Ver</th>
                      <th className="px-4 py-3 font-semibold">Updated</th>
                      <th className="px-4 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredReports.map((rf) => (
                      <tr key={rf.id} className="hover:bg-slate-50/70">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[#173042]">{rf.zone_name}</p>
                          <p className="text-[11px] text-[#718096]">{rf.region_name}</p>
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-[#173042]">{rf.original_filename}</p>
                          <p className="text-[11px] text-[#718096]">{formatBytes(rf.file_size)}</p>
                        </td>
                        <td className="px-4 py-3 font-semibold">{rf.row_count}</td>
                        <td className="px-4 py-3 font-mono font-semibold text-[#075D6B]">
                          v{rf.version}
                        </td>
                        <td className="px-4 py-3 text-[#718096]">{formatDateTime(rf.uploaded_at)}</td>
                        <td className="px-4 py-3 text-right">
                          <div className="inline-flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => setPreviewTarget({ id: rf.id })}
                              className="rounded-lg border border-slate-200 px-2.5 py-1 font-semibold text-[#173042] hover:bg-slate-100"
                            >
                              Preview
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                reportFilesApi.download(reportType, rf.id, rf.original_filename)
                              }
                              className="rounded-lg bg-[#075D6B] px-2.5 py-1 font-semibold text-white hover:bg-[#0D7780]"
                            >
                              Download
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      <ExcelPreviewModal
        open={previewTarget !== null}
        reportType={reportType}
        reportId={previewTarget?.id ?? null}
        version={previewTarget?.version}
        onClose={() => setPreviewTarget(null)}
      />

      <ConfirmModal
        open={deleteTarget !== null}
        title={`Delete ${title}?`}
        message={`This will deactivate "${deleteTarget?.original_filename}" for zone "${deleteTarget?.zone_name}" and mark any generated Merged Report for this zone as outdated.`}
        confirmLabel="Delete File"
        danger
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

