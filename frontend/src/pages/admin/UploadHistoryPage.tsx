import { useCallback, useEffect, useState } from "react";
import { Download, History } from "lucide-react";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { adminApi, reportFilesApi } from "../../services/endpoints";
import type { ReportType, UploadHistoryItem } from "../../types";
import { formatBytes, formatDateTime, formatReportType } from "../../utils/format";
import { StatusBadge } from "../../components/common/StatusBadge";

export function UploadHistoryPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<UploadHistoryItem[]>([]);
  const [filterType, setFilterType] = useState<"" | ReportType>("");
  const [loading, setLoading] = useState(true);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.listUploadHistory(filterType || undefined);
      setItems(data);
    } catch (err) {
      showToast("error", "Load Failed", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [filterType, showToast]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#173042]">Upload History &amp; File Versions</h1>
          <p className="mt-1 text-sm text-[#718096]">
            Complete immutable archive of every Pole Survey and Lamp Installation upload version.
          </p>
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as "" | ReportType)}
          className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-[#173042]"
        >
          <option value="">All Report Types</option>
          <option value="pole_survey">Pole Survey Reports</option>
          <option value="lamp_installation">Lamp Installation Reports</option>
        </select>
      </div>

      <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex items-center gap-2">
          <History className="h-4 w-4 text-[#075D6B]" />
          <h2 className="text-sm font-bold text-[#173042]">Version Records ({items.length})</h2>
        </div>

        {loading ? (
          <p className="p-6 text-center text-xs text-[#718096]">Loading upload history...</p>
        ) : items.length === 0 ? (
          <p className="p-8 text-center text-xs text-[#718096]">No uploads recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[#718096]">
                <tr>
                  <th className="px-4 py-3 font-semibold">Module</th>
                  <th className="px-4 py-3 font-semibold">Customer / Region / Zone</th>
                  <th className="px-4 py-3 font-semibold">Filename</th>
                  <th className="px-4 py-3 font-semibold">Version</th>
                  <th className="px-4 py-3 font-semibold">Rows / Size</th>
                  <th className="px-4 py-3 font-semibold">Uploaded By</th>
                  <th className="px-4 py-3 font-semibold text-right">Download</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-semibold text-[#075D6B]">
                      {formatReportType(item.report_type)}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-[#173042]">{item.zone_name}</p>
                      <p className="text-[11px] text-[#718096]">
                        {item.customer_name} • {item.region_name}
                      </p>
                    </td>
                    <td className="px-4 py-3 font-medium text-[#173042]">
                      {item.original_filename}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-[#075D6B]">
                          v{item.version}
                        </span>
                        <StatusBadge
                          status={
                            item.is_current
                              ? "active"
                              : item.file_status === "deleted"
                              ? "deleted"
                              : "superseded"
                          }
                          label={item.is_current ? "Current" : item.file_status === "deleted" ? "Deleted" : "Archived"}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[#718096]">
                      {item.row_count} rows • {formatBytes(item.file_size)}
                    </td>
                    <td className="px-4 py-3 text-[#718096]">
                      <p>{item.uploaded_by_name || "Admin"}</p>
                      <p className="text-[11px]">{formatDateTime(item.uploaded_at)}</p>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() =>
                          reportFilesApi.download(
                            item.report_type,
                            item.report_file_id,
                            item.original_filename,
                            item.version
                          )
                        }
                        className="inline-flex items-center gap-1 rounded-lg bg-[#075D6B] px-2.5 py-1 font-semibold text-white hover:bg-[#0D7780]"
                      >
                        <Download className="h-3 w-3" />
                        v{item.version}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

