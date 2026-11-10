import React, { useRef, useState } from "react";
import { AlertCircle, CheckCircle2, FileSpreadsheet, UploadCloud, X } from "lucide-react";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { reportFilesApi } from "../../services/endpoints";
import type { ReportFile, ReportType } from "../../types";
import { formatBytes } from "../../utils/format";
import { ConfirmModal } from "../common/ConfirmModal";

export function ReportUploadPanel({
  reportType,
  customerId,
  regionId,
  zoneId,
  zoneName,
  existingReport,
  onUploaded,
}: {
  reportType: ReportType;
  customerId: number;
  regionId: number;
  zoneId: number;
  zoneName: string;
  existingReport: ReportFile | null;
  onUploaded: (file: ReportFile) => void;
}) {
  const { showToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [confirmReplaceOpen, setConfirmReplaceOpen] = useState(false);

  const label = reportType === "pole_survey" ? "Pole Survey Report" : "Lamp Installation Report";

  const handleFilePick = (file: File | null) => {
    setErrorMsg(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const lower = file.name.toLowerCase();
    if (!lower.endsWith(".xlsx") && !lower.endsWith(".xls")) {
      setErrorMsg("Unsupported file type. Please choose a valid .xlsx or .xls workbook.");
      return;
    }
    setSelectedFile(file);
  };

  const executeUpload = async (replaceExisting: boolean) => {
    if (!selectedFile) return;
    setUploading(true);
    setProgress(0);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append("customer_id", String(customerId));
    formData.append("region_id", String(regionId));
    formData.append("zone_id", String(zoneId));
    formData.append("replace_existing", String(replaceExisting));
    formData.append("file", selectedFile);

    try {
      const saved = await reportFilesApi.upload(reportType, formData, setProgress);
      showToast(
        "success",
        `${label} Uploaded`,
        `${saved.original_filename} (v${saved.version}, ${saved.row_count} rows) saved for ${zoneName}.`
      );
      setSelectedFile(null);
      setConfirmReplaceOpen(false);
      if (inputRef.current) inputRef.current.value = "";
      onUploaded(saved);
    } catch (err) {
      const msg = extractErrorMessage(err);
      setErrorMsg(msg);
      showToast("error", "Upload Failed", msg);
    } finally {
      setUploading(false);
    }
  };

  const handleConfirmClick = () => {
    if (!selectedFile) return;
    if (existingReport) {
      setConfirmReplaceOpen(true);
    } else {
      executeUpload(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-[#173042]">
            {existingReport ? `Replace ${label}` : `Upload ${label}`}
          </h3>
          <p className="text-xs text-[#718096] mt-0.5">
            Target Zone: <strong className="text-[#075D6B]">{zoneName}</strong> • Supports .xlsx
            (recommended for formatting) and .xls
          </p>
        </div>
        {reportType === "lamp_installation" && (
          <span className="rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-[11px] font-semibold text-[#075D6B]">
            Master Formatting Template
          </span>
        )}
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0] || null;
          handleFilePick(f);
        }}
        onClick={() => inputRef.current?.click()}
        className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-7 text-center transition ${
          dragging
            ? "border-[#18A6A0] bg-teal-50/70"
            : "border-slate-300 bg-slate-50/60 hover:border-[#0D7780] hover:bg-teal-50/30"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={(e) => handleFilePick(e.target.files?.[0] || null)}
        />
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#075D6B]/10 text-[#075D6B]">
          <UploadCloud className="h-6 w-6" />
        </div>
        <p className="mt-3 text-sm font-semibold text-[#173042]">
          Drag and drop your Excel workbook here, or{" "}
          <span className="text-[#0D7780] underline">browse file</span>
        </p>
        <p className="mt-1 text-xs text-[#718096]">Maximum file size: 25 MB</p>
      </div>

      {/* Selected file preview bar */}
      {selectedFile && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-teal-200 bg-teal-50/50 p-3.5">
          <div className="flex items-center gap-3 min-w-0">
            <FileSpreadsheet className="h-5 w-5 text-[#075D6B] shrink-0" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-[#173042]">{selectedFile.name}</p>
              <p className="text-xs text-[#718096]">
                {formatBytes(selectedFile.size)} • Ready to validate &amp; upload
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={uploading}
              onClick={() => {
                setSelectedFile(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
              className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-500 hover:bg-slate-100"
            >
              <X className="h-4 w-4" />
            </button>
            <button
              type="button"
              disabled={uploading}
              onClick={handleConfirmClick}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#075D6B] px-4 py-2 text-xs font-semibold text-white hover:bg-[#0D7780] disabled:opacity-50 transition"
            >
              <CheckCircle2 className="h-4 w-4" />
              {uploading
                ? `Uploading (${progress}%)`
                : existingReport
                ? "Replace & Save Version"
                : "Validate & Upload"}
            </button>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      {uploading && (
        <div className="mt-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full bg-[#18A6A0] transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Validation Error */}
      {errorMsg && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      <ConfirmModal
        open={confirmReplaceOpen}
        title={`Replace Existing ${label}?`}
        message={`Zone "${zoneName}" already has "${existingReport?.original_filename}" (v${existingReport?.version}). Uploading "${selectedFile?.name}" will create version ${(existingReport?.version ?? 0) + 1} while preserving previous versions in upload history, and will mark any existing Merged Report for this zone as outdated.`}
        confirmLabel="Confirm Replacement"
        loading={uploading}
        onConfirm={() => executeUpload(true)}
        onCancel={() => setConfirmReplaceOpen(false)}
      />
    </div>
  );
}

