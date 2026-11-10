import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  Search,
  X,
} from "lucide-react";
import { extractErrorMessage } from "../../services/api";
import { reportFilesApi } from "../../services/endpoints";
import type { ExcelPreview, ReportType } from "../../types";

export function ExcelPreviewModal({
  open,
  reportType,
  reportId,
  version,
  onClose,
}: {
  open: boolean;
  reportType: ReportType;
  reportId: number | null;
  version?: number;
  onClose: () => void;
}) {
  const [data, setData] = useState<ExcelPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetName, setSheetName] = useState<string | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [filterColumn, setFilterColumn] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!open || !reportId) return;
    let active = true;
    setLoading(true);
    setError(null);

    reportFilesApi
      .preview(reportType, reportId, {
        version,
        sheet_name: sheetName,
        search: search || undefined,
        filter_column: filterColumn || undefined,
        filter_value: filterValue || undefined,
        page,
        page_size: 50,
      })
      .then((res) => {
        if (!active) return;
        setData(res);
      })
      .catch((err) => {
        if (!active) return;
        setError(extractErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [open, reportType, reportId, version, sheetName, search, filterColumn, filterValue, page]);

  useEffect(() => {
    setSheetName(undefined);
    setSearch("");
    setFilterColumn("");
    setFilterValue("");
    setPage(1);
  }, [reportId, version, open]);

  if (!open || !reportId) return null;

  const totalPages = data ? Math.max(1, Math.ceil(data.total_rows / data.page_size)) : 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-[1px] p-3 sm:p-6">
      <div className="flex h-[88vh] w-full max-w-6xl flex-col rounded-2xl border border-slate-200 bg-white shadow-elevated overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 bg-[#075D6B] px-5 py-3.5 text-white">
          <div className="flex items-center gap-3 min-w-0">
            <FileSpreadsheet className="h-5 w-5 text-teal-200 shrink-0" />
            <div className="min-w-0">
              <h3 className="truncate text-sm font-bold">
                {data?.original_filename || "Workbook Preview"}
              </h3>
              <p className="text-[11px] text-teal-100/80">
                Version {data?.version ?? version ?? "Latest"} •{" "}
                {data ? `${data.total_rows} records` : "Loading..."}
                {data ? ` • Header Row ${data.header_row_index}` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {data && (
              <button
                type="button"
                onClick={() =>
                  reportFilesApi.download(reportType, reportId, data.original_filename, data.version)
                }
                className="inline-flex items-center gap-1.5 rounded-lg bg-[#18A6A0] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#0D7780] transition"
              >
                <Download className="h-3.5 w-3.5" />
                Download
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-teal-100 hover:bg-white/15 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Filters bar */}
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-slate-50 px-5 py-3">
          {data && data.sheets.length > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[#718096]">Sheet:</span>
              <select
                value={sheetName || data.active_sheet}
                onChange={(e) => {
                  setSheetName(e.target.value);
                  setPage(1);
                }}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-[#173042]"
              >
                {data.sheets.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="relative flex-1 min-w-[200px]">
            <Search className="pointer-events-none absolute left-3 top-2 h-4 w-4 text-[#718096]" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search records across all columns..."
              className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-xs text-[#173042] focus:border-[#18A6A0] focus:outline-none"
            />
          </div>

          {data && data.columns.length > 0 && (
            <div className="flex items-center gap-2">
              <select
                value={filterColumn}
                onChange={(e) => {
                  setFilterColumn(e.target.value);
                  setPage(1);
                }}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-[#173042]"
              >
                <option value="">Filter column...</option>
                {data.columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              {filterColumn && (
                <input
                  type="text"
                  value={filterValue}
                  onChange={(e) => {
                    setFilterValue(e.target.value);
                    setPage(1);
                  }}
                  placeholder="Contains..."
                  className="w-36 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-[#173042]"
                />
              )}
            </div>
          )}
        </div>

        {/* Warnings */}
        {data && data.warnings.length > 0 && (
          <div className="border-b border-amber-200 bg-amber-50 px-5 py-2 flex items-start gap-2 text-xs text-amber-800">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />
            <div className="space-y-0.5">
              {data.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          </div>
        )}

        {/* Table Body */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex h-full items-center justify-center text-sm text-[#718096]">
              Loading workbook records...
            </div>
          ) : error ? (
            <div className="m-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              {error}
            </div>
          ) : !data || data.rows.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-[#718096]">
              No matching records found.
            </div>
          ) : (
            <table className="min-w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 z-10 bg-slate-100 text-[#173042] shadow-sm">
                <tr>
                  <th className="border-b border-r border-slate-200 px-3 py-2.5 font-bold w-16 text-center">
                    Row
                  </th>
                  {data.columns.map((col) => (
                    <th
                      key={col}
                      className="border-b border-r border-slate-200 px-3 py-2.5 font-bold whitespace-nowrap"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.rows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-teal-50/40 transition-colors">
                    <td className="border-r border-slate-100 bg-slate-50/70 px-3 py-2 text-center font-mono text-[11px] text-[#718096]">
                      {row._excel_row}
                    </td>
                    {data.columns.map((col) => (
                      <td
                        key={col}
                        className="border-r border-slate-100 px-3 py-2 text-[#173042] whitespace-nowrap max-w-xs truncate"
                        title={String(row[col] ?? "")}
                      >
                        {row[col] || <span className="text-slate-300">—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {data && (
          <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-5 py-2.5 text-xs text-[#718096]">
            <span>
              Page <strong className="text-[#173042]">{data.page}</strong> of{" "}
              <strong className="text-[#173042]">{totalPages}</strong> ({data.total_rows} total rows)
            </span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-semibold text-[#173042] hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Prev
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 font-semibold text-[#173042] hover:bg-slate-100 disabled:opacity-40"
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

