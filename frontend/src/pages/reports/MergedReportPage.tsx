import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Eye,
  FileSpreadsheet,
  GitMerge,
  History,
  Info,
  Play,
  Plus,
  Search,
  Send,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { mergedReportsApi } from "../../services/endpoints";
import type {
  MappingInput,
  MergedReport,
  MergedReportInspect,
  MergedReportPreview,
} from "../../types";
import { formatBytes, formatDateTime } from "../../utils/format";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { StatusBadge } from "../../components/common/StatusBadge";
import { HierarchyExplorer } from "../../components/hierarchy/HierarchyExplorer";

type PreviewTab =
  | "summary"
  | "added"
  | "existing"
  | "skipped"
  | "duplicates"
  | "invalid";

export function MergedReportPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { selection, selectedCustomer, selectedRegion, selectedZone, refreshTree } = useHierarchy();
  const { showToast } = useToast();

  const isAdmin = user?.role === "admin";

  const [reports, setReports] = useState<MergedReport[]>([]);
  const [loadingList, setLoadingList] = useState(false);

  // Admin inspection & mapping state
  const [inspectData, setInspectData] = useState<MergedReportInspect | null>(null);
  const [inspecting, setInspecting] = useState(false);
  const [poleMap, setPoleMap] = useState<MappingInput>({
    pole_number_col: "",
    arm_count_col: "",
    lamp_type_col: "",
  });
  const [lampMap, setLampMap] = useState<MappingInput>({
    pole_number_col: "",
    arm_count_col: "",
    lamp_type_col: "",
  });
  const [extraMappings, setExtraMappings] = useState<{ surveyCol: string; lampCol: string }[]>([]);
  const [saveMapping, setSaveMapping] = useState(true);
  const [generating, setGenerating] = useState(false);

  // Preview & Publish state
  const [previewData, setPreviewData] = useState<MergedReportPreview | null>(null);
  const [previewedVersion, setPreviewedVersion] = useState<number | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [activeTab, setActiveTab] = useState<PreviewTab>("summary");
  const [previewSearch, setPreviewSearch] = useState("");
  const [publishConfirmId, setPublishConfirmId] = useState<number | null>(null);
  const [publishing, setPublishing] = useState(false);

  const loadReports = useCallback(async () => {
    setLoadingList(true);
    try {
      const list = await mergedReportsApi.list({
        customer_id: selection.customerId ?? undefined,
      });
      setReports(list);
    } catch (err) {
      showToast("error", "Failed to load Merged Reports", extractErrorMessage(err));
    } finally {
      setLoadingList(false);
    }
  }, [selection.customerId, showToast]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const inspectZone = useCallback(
    async (
      overrides?: {
        pole_sheet?: string;
        pole_header_row?: number;
        lamp_sheet?: string;
        lamp_header_row?: number;
      },
      scope: "all" | "pole" | "lamp" = "all"
    ) => {
      if (!isAdmin || !selection.customerId || !selection.regionId || !selection.zoneId) {
        setInspectData(null);
        return;
      }
      setInspecting(true);
      try {
        const res = await mergedReportsApi.inspect({
          customer_id: selection.customerId,
          region_id: selection.regionId,
          zone_id: selection.zoneId,
          ...overrides,
        });
        setInspectData(res);

        // Initialize mappings from saved mapping or suggested auto-detection
        if (scope === "all" || scope === "pole") {
          const pSaved = res.pole_survey_saved_mapping;
          setPoleMap({
            sheet_name: overrides?.pole_sheet || pSaved?.sheet_name || res.pole_survey_active_sheet || undefined,
            header_row_index:
              overrides?.pole_header_row || pSaved?.header_row_index || res.pole_survey_header_row || 1,
            pole_number_col:
              pSaved?.pole_number_col || res.pole_survey_suggested_mapping?.pole_number || "",
            arm_count_col:
              pSaved?.arm_count_col || res.pole_survey_suggested_mapping?.arm_count || "",
            lamp_type_col:
              pSaved?.lamp_type_col || res.pole_survey_suggested_mapping?.lamp_type || "",
          });

          const savedExtras = pSaved?.extra_mappings as Record<string, string> | undefined;
          if (savedExtras && typeof savedExtras === "object") {
            setExtraMappings(
              Object.entries(savedExtras).map(([surveyCol, lampCol]) => ({
                surveyCol,
                lampCol,
              }))
            );
          } else if (scope === "all") {
            setExtraMappings([]);
          }
        }

        if (scope === "all" || scope === "lamp") {
          const lSaved = res.lamp_saved_mapping;
          setLampMap({
            sheet_name: overrides?.lamp_sheet || lSaved?.sheet_name || res.lamp_active_sheet || undefined,
            header_row_index:
              overrides?.lamp_header_row || lSaved?.header_row_index || res.lamp_header_row || 1,
            pole_number_col:
              lSaved?.pole_number_col || res.lamp_suggested_mapping?.pole_number || "",
            arm_count_col: lSaved?.arm_count_col || res.lamp_suggested_mapping?.arm_count || "",
            lamp_type_col: lSaved?.lamp_type_col || res.lamp_suggested_mapping?.lamp_type || "",
          });
        }
      } catch (err) {
        showToast("error", "Source Inspection Failed", extractErrorMessage(err));
      } finally {
        setInspecting(false);
      }
    },
    [isAdmin, selection.customerId, selection.regionId, selection.zoneId, showToast]
  );

  useEffect(() => {
    inspectZone();
  }, [inspectZone]);

  const activeZoneReport =
    selection.zoneId != null
      ? reports.find((r) => r.zone_id === selection.zoneId) ?? null
      : null;

  const loadPreview = useCallback(
    async (mergedId: number, version?: number) => {
      setLoadingPreview(true);
      try {
        const res = await mergedReportsApi.preview(mergedId, version);
        setPreviewData(res);
        setPreviewedVersion(version ?? res.merged_report.current_version);
        setPreviewSearch("");
      } catch (err) {
        showToast("error", "Preview Load Failed", extractErrorMessage(err));
      } finally {
        setLoadingPreview(false);
      }
    },
    [showToast]
  );

  // Auto-load preview when zone has an existing Merged Report
  useEffect(() => {
    if (activeZoneReport) {
      loadPreview(activeZoneReport.id);
    } else {
      setPreviewData(null);
      setPreviewedVersion(null);
    }
  }, [activeZoneReport?.id, activeZoneReport?.current_version, loadPreview]);

  const handleGenerate = async () => {
    if (!selection.customerId || !selection.regionId || !selection.zoneId) return;
    if (!poleMap.pole_number_col || !poleMap.arm_count_col || !poleMap.lamp_type_col) {
      showToast(
        "error",
        "Column Mapping Incomplete",
        "Please map Pole Number, Arm Count, and Lamp Type for the Pole Survey workbook."
      );
      return;
    }
    if (!lampMap.pole_number_col) {
      showToast(
        "error",
        "Column Mapping Incomplete",
        "Please map the Pole Number column for the Lamp Installation workbook."
      );
      return;
    }

    const validExtras: Record<string, string> = {};
    for (const pair of extraMappings) {
      if (pair.surveyCol && pair.lampCol) {
        validExtras[pair.surveyCol] = pair.lampCol;
      }
    }

    setGenerating(true);
    try {
      const res = await mergedReportsApi.generate({
        customer_id: selection.customerId,
        region_id: selection.regionId,
        zone_id: selection.zoneId,
        pole_survey_mapping: {
          ...poleMap,
          extra_mappings: validExtras,
        },
        lamp_installation_mapping: {
          ...lampMap,
          arm_count_col: lampMap.arm_count_col || null,
          lamp_type_col: lampMap.lamp_type_col || null,
        },
        save_mapping: saveMapping,
      });
      setPreviewData(res);
      setPreviewedVersion(res.merged_report.current_version);
      setActiveTab("summary");
      showToast(
        "success",
        "Merged Report Generated",
        `Added ${res.summary.added_records} new LED pole(s). Review summary & tabs before publishing.`
      );
      await Promise.all([loadReports(), refreshTree()]);
    } catch (err) {
      showToast("error", "Generation Failed", extractErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const handlePublish = async () => {
    if (!publishConfirmId) return;
    setPublishing(true);
    try {
      await mergedReportsApi.publish(publishConfirmId);
      showToast(
        "success",
        "Merged Report Published",
        "Customers assigned to this region can now view and download this report."
      );
      setPublishConfirmId(null);
      await Promise.all([loadReports(), refreshTree()]);
      if (previewData?.merged_report.id === publishConfirmId) {
        await loadPreview(publishConfirmId);
      }
    } catch (err) {
      showToast("error", "Publish Failed", extractErrorMessage(err));
    } finally {
      setPublishing(false);
    }
  };

  const visibleReports = reports.filter((r) => {
    if (selection.zoneId) return r.zone_id === selection.zoneId;
    if (selection.regionId) return r.region_id === selection.regionId;
    return true;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">Merged Reports &amp; LED Reconciliation</h1>
        <p className="mt-1 text-sm text-[#718096]">
          {isAdmin
            ? "Zone-isolated reconciliation engine preserving original Lamp Installation Excel formatting."
            : "View processing summaries, preview records, and download published Merged Reports."}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Zone Selector */}
        <div className="lg:col-span-4">
          <HierarchyExplorer />
        </div>

        {/* Right Merged Report Workspace */}
        <div className="lg:col-span-8 space-y-6">
          {/* Admin Source Inspection & Mapping Panel */}
          {isAdmin && (
            <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3.5">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#075D6B]/10 text-[#075D6B]">
                    <GitMerge className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-[#173042]">
                      Zone Reconciliation Workspace
                    </h2>
                    <p className="text-xs text-[#718096]">
                      {selectedZone
                        ? `${selectedCustomer?.customer_name} → ${selectedRegion?.region_name} → ${selectedZone.zone_name}`
                        : "Select a specific zone on the left to inspect sources and generate"}
                    </p>
                  </div>
                </div>
                {activeZoneReport && <StatusBadge status={activeZoneReport.status} />}
              </div>

              {!selectedZone ? (
                <p className="py-8 text-center text-sm text-[#718096]">
                  Please select a <strong className="text-[#075D6B]">Zone</strong> from the hierarchy
                  navigator to begin.
                </p>
              ) : inspecting ? (
                <p className="py-8 text-center text-xs text-[#718096]">
                  Inspecting Pole Survey and Lamp Installation workbooks...
                </p>
              ) : inspectData ? (
                <div className="mt-4 space-y-5">
                  {/* Outdated warning */}
                  {activeZoneReport?.is_outdated && (
                    <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                      <div>
                        <p className="font-bold">Merged Report is Outdated</p>
                        <p className="mt-0.5">
                          Generated from Pole Survey v{activeZoneReport.source_pole_survey_version}{" "}
                          and Lamp Installation v{activeZoneReport.source_lamp_installation_version}.
                          Active versions are Pole Survey v
                          {activeZoneReport.active_pole_survey_version ?? "missing"} and Lamp
                          Installation v
                          {activeZoneReport.active_lamp_installation_version ?? "missing"}.
                          Regenerate below to update.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Missing source blocking error */}
                  {inspectData.blocking_error && (
                    <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
                      <AlertTriangle className="h-5 w-5 shrink-0 text-rose-600" />
                      <div>
                        <p className="font-bold">Source Files Missing</p>
                        <p className="mt-0.5">{inspectData.blocking_error}</p>
                      </div>
                    </div>
                  )}

                  {/* Source file badges */}
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div
                      className={`rounded-xl border p-3.5 text-xs ${
                        inspectData.pole_survey_ready
                          ? "border-emerald-200 bg-emerald-50/40"
                          : "border-rose-200 bg-rose-50/40"
                      }`}
                    >
                      <p className="font-bold text-[#173042]">A. Pole Survey Report</p>
                      {inspectData.pole_survey_file ? (
                        <p className="mt-1 text-[#718096]">
                          <strong className="text-[#075D6B]">
                            {inspectData.pole_survey_file.original_filename}
                          </strong>{" "}
                          (v{inspectData.pole_survey_file.version} •{" "}
                          {inspectData.pole_survey_file.row_count} rows)
                        </p>
                      ) : (
                        <p className="mt-1 text-rose-700 font-medium">Not uploaded for this zone</p>
                      )}
                    </div>

                    <div
                      className={`rounded-xl border p-3.5 text-xs ${
                        inspectData.lamp_installation_ready
                          ? "border-emerald-200 bg-emerald-50/40"
                          : "border-rose-200 bg-rose-50/40"
                      }`}
                    >
                      <p className="font-bold text-[#173042]">
                        B. Lamp Installation Report (Master Template)
                      </p>
                      {inspectData.lamp_installation_file ? (
                        <p className="mt-1 text-[#718096]">
                          <strong className="text-[#075D6B]">
                            {inspectData.lamp_installation_file.original_filename}
                          </strong>{" "}
                          (v{inspectData.lamp_installation_file.version} •{" "}
                          {inspectData.lamp_installation_file.row_count} rows)
                        </p>
                      ) : (
                        <p className="mt-1 text-rose-700 font-medium">Not uploaded for this zone</p>
                      )}
                    </div>
                  </div>

                  {/* Column Mapping Interface when both files exist */}
                  {!inspectData.blocking_error && (
                    <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-4">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <SlidersHorizontal className="h-4 w-4 text-[#075D6B]" />
                          <h3 className="text-xs font-bold uppercase tracking-wider text-[#173042]">
                            Worksheet, Header Row &amp; Column Mapping
                          </h3>
                        </div>
                        {(inspectData.pole_survey_saved_mapping ||
                          inspectData.lamp_saved_mapping) && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-teal-50 border border-teal-200 px-2.5 py-0.5 text-[11px] font-semibold text-[#075D6B]">
                            <CheckCircle2 className="h-3 w-3" /> Saved Mapping Loaded
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        {/* Pole Survey Mapping */}
                        <div className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2.5">
                          <p className="text-xs font-bold text-[#075D6B]">
                            Pole Survey Columns (Extract Only)
                          </p>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-[11px] font-semibold text-[#718096]">
                                Sheet
                              </label>
                              <select
                                value={poleMap.sheet_name || ""}
                                onChange={(e) =>
                                  inspectZone(
                                    {
                                      pole_sheet: e.target.value,
                                      pole_header_row: poleMap.header_row_index ?? undefined,
                                      lamp_sheet: lampMap.sheet_name ?? undefined,
                                      lamp_header_row: lampMap.header_row_index ?? undefined,
                                    },
                                    "pole"
                                  )
                                }
                                className="mt-0.5 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
                              >
                                {inspectData.pole_survey_sheets.map((s) => (
                                  <option key={s} value={s}>
                                    {s}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-[#718096]">
                                Header Row
                              </label>
                              <input
                                type="number"
                                min={1}
                                max={50}
                                value={poleMap.header_row_index ?? 1}
                                onChange={(e) =>
                                  inspectZone(
                                    {
                                      pole_sheet: poleMap.sheet_name ?? undefined,
                                      pole_header_row: Number(e.target.value) || 1,
                                      lamp_sheet: lampMap.sheet_name ?? undefined,
                                      lamp_header_row: lampMap.header_row_index ?? undefined,
                                    },
                                    "pole"
                                  )
                                }
                                className="mt-0.5 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
                              />
                            </div>
                          </div>

                          {[
                            { key: "pole_number_col", label: "Pole Number *" },
                            { key: "arm_count_col", label: "Arm Count *" },
                            { key: "lamp_type_col", label: "Lamp Type *" },
                          ].map((field) => (
                            <div key={field.key}>
                              <label className="block text-[11px] font-semibold text-[#173042]">
                                {field.label}
                              </label>
                              <select
                                value={(poleMap as any)[field.key] || ""}
                                onChange={(e) =>
                                  setPoleMap((prev) => ({ ...prev, [field.key]: e.target.value }))
                                }
                                className="mt-0.5 w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                              >
                                <option value="">-- Select Column --</option>
                                {inspectData.pole_survey_headers.map((h) => (
                                  <option key={h} value={h}>
                                    {h}
                                  </option>
                                ))}
                              </select>
                            </div>
                          ))}
                        </div>

                        {/* Lamp Installation Mapping */}
                        <div className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2.5">
                          <p className="text-xs font-bold text-[#075D6B]">
                            Lamp Installation Target Columns
                          </p>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="block text-[11px] font-semibold text-[#718096]">
                                Sheet
                              </label>
                              <select
                                value={lampMap.sheet_name || ""}
                                onChange={(e) =>
                                  inspectZone(
                                    {
                                      pole_sheet: poleMap.sheet_name ?? undefined,
                                      pole_header_row: poleMap.header_row_index ?? undefined,
                                      lamp_sheet: e.target.value,
                                      lamp_header_row: lampMap.header_row_index ?? undefined,
                                    },
                                    "lamp"
                                  )
                                }
                                className="mt-0.5 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
                              >
                                {inspectData.lamp_sheets.map((s) => (
                                  <option key={s} value={s}>
                                    {s}
                                  </option>
                                ))}
                              </select>
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-[#718096]">
                                Header Row
                              </label>
                              <input
                                type="number"
                                min={1}
                                max={50}
                                value={lampMap.header_row_index ?? 1}
                                onChange={(e) =>
                                  inspectZone(
                                    {
                                      pole_sheet: poleMap.sheet_name ?? undefined,
                                      pole_header_row: poleMap.header_row_index ?? undefined,
                                      lamp_sheet: lampMap.sheet_name ?? undefined,
                                      lamp_header_row: Number(e.target.value) || 1,
                                    },
                                    "lamp"
                                  )
                                }
                                className="mt-0.5 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
                              />
                            </div>
                          </div>

                          {[
                            { key: "pole_number_col", label: "Pole Number Cell (Writes P...-Ln) *" },
                            { key: "arm_count_col", label: "Arm Count (Optional)" },
                            { key: "lamp_type_col", label: "Lamp Type (Optional)" },
                          ].map((field) => (
                            <div key={field.key}>
                              <label className="block text-[11px] font-semibold text-[#173042]">
                                {field.label}
                              </label>
                              <select
                                value={(lampMap as any)[field.key] || ""}
                                onChange={(e) =>
                                  setLampMap((prev) => ({ ...prev, [field.key]: e.target.value }))
                                }
                                className="mt-0.5 w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                              >
                                <option value="">-- Leave Blank / Unmapped --</option>
                                {inspectData.lamp_headers.map((h) => (
                                  <option key={h} value={h}>
                                    {h}
                                  </option>
                                ))}
                              </select>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Optional Additional Field Mappings */}
                      <div className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="text-xs font-bold text-[#173042]">
                              Additional Column Mappings (Optional)
                            </p>
                            <p className="text-[11px] text-[#718096]">
                              Optionally copy matching metadata columns (e.g. Road Name, Ward, Remarks). Unmapped template columns always remain blank.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() =>
                              setExtraMappings((prev) => [...prev, { surveyCol: "", lampCol: "" }])
                            }
                            className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-semibold text-[#075D6B] hover:bg-teal-50"
                          >
                            <Plus className="h-3.5 w-3.5" /> Add Field Pair
                          </button>
                        </div>

                        {extraMappings.length > 0 && (
                          <div className="space-y-2 pt-1">
                            {extraMappings.map((pair, idx) => (
                              <div key={idx} className="grid grid-cols-1 gap-2 sm:grid-cols-11 items-center">
                                <select
                                  value={pair.surveyCol}
                                  onChange={(e) =>
                                    setExtraMappings((prev) =>
                                      prev.map((item, i) =>
                                        i === idx ? { ...item, surveyCol: e.target.value } : item
                                      )
                                    )
                                  }
                                  className="sm:col-span-5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                                >
                                  <option value="">-- Pole Survey Source Column --</option>
                                  {inspectData.pole_survey_headers.map((h) => (
                                    <option key={h} value={h}>
                                      {h}
                                    </option>
                                  ))}
                                </select>
                                <span className="sm:col-span-1 text-center text-xs font-bold text-[#718096]">
                                  →
                                </span>
                                <select
                                  value={pair.lampCol}
                                  onChange={(e) =>
                                    setExtraMappings((prev) =>
                                      prev.map((item, i) =>
                                        i === idx ? { ...item, lampCol: e.target.value } : item
                                      )
                                    )
                                  }
                                  className="sm:col-span-4 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                                >
                                  <option value="">-- Lamp Install Target Column --</option>
                                  {inspectData.lamp_headers.map((h) => (
                                    <option key={h} value={h}>
                                      {h}
                                    </option>
                                  ))}
                                </select>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExtraMappings((prev) => prev.filter((_, i) => i !== idx))
                                  }
                                  className="sm:col-span-1 inline-flex justify-center rounded-lg p-1.5 text-rose-600 hover:bg-rose-50"
                                  title="Remove mapping pair"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {inspectData.warnings.length > 0 && (
                        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 space-y-1">
                          {inspectData.warnings.map((w, idx) => (
                            <p key={idx} className="flex items-start gap-1.5">
                              <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                              <span>{w}</span>
                            </p>
                          ))}
                        </div>
                      )}

                      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                        <label className="flex items-center gap-2 text-xs text-[#718096] cursor-pointer">
                          <input
                            type="checkbox"
                            checked={saveMapping}
                            onChange={(e) => setSaveMapping(e.target.checked)}
                            className="h-4 w-4 rounded border-slate-300 text-[#075D6B]"
                          />
                          Save confirmed mappings for future uploads with the same headers
                        </label>

                        <button
                          type="button"
                          disabled={generating}
                          onClick={handleGenerate}
                          className="inline-flex items-center gap-2 rounded-xl bg-[#075D6B] px-5 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-[#0D7780] disabled:opacity-50 transition"
                        >
                          <Play className="h-4 w-4" />
                          {generating
                            ? "Processing Reconciliation..."
                            : activeZoneReport
                            ? "Regenerate Merged Report"
                            : "Generate Merged Report"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}

          {/* 6-Tab Preview & Summary Section */}
          {(loadingPreview || previewData) && (
            <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
              {loadingPreview ? (
                <p className="p-8 text-center text-xs text-[#718096]">
                  Loading Merged Report preview &amp; summary...
                </p>
              ) : previewData ? (
                <>
                  {/* Preview Top Header */}
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-4">
                    <div>
                      <div className="flex items-center gap-2.5">
                        <h3 className="text-sm font-bold text-[#173042]">
                          {previewData.merged_report.zone_name} — Merged Report v
                          {previewedVersion ?? previewData.merged_report.current_version}
                        </h3>
                        <StatusBadge
                          status={
                            previewedVersion != null &&
                            previewedVersion !== previewData.merged_report.current_version
                              ? previewData.merged_report.versions.find(
                                  (v) => v.version === previewedVersion
                                )?.status || previewData.merged_report.status
                              : previewData.merged_report.status
                          }
                        />
                      </div>
                      <p className="mt-0.5 text-xs text-[#718096]">
                        {(() => {
                          const targetVer = previewData.merged_report.versions.find(
                            (v) =>
                              v.version ===
                              (previewedVersion ?? previewData.merged_report.current_version)
                          );
                          const psVer =
                            targetVer?.source_pole_survey_version ??
                            previewData.merged_report.source_pole_survey_version;
                          const liVer =
                            targetVer?.source_lamp_installation_version ??
                            previewData.merged_report.source_lamp_installation_version;
                          return (
                            <>
                              Source Versions: Pole Survey v{psVer} &amp; Lamp Installation v
                              {liVer}
                            </>
                          );
                        })()}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {previewedVersion != null &&
                        previewedVersion !== previewData.merged_report.current_version && (
                          <button
                            type="button"
                            onClick={() => loadPreview(previewData.merged_report.id)}
                            className="inline-flex items-center gap-1 rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs font-semibold text-[#075D6B] hover:bg-teal-100"
                          >
                            View Latest (v{previewData.merged_report.current_version})
                          </button>
                        )}
                      <button
                        type="button"
                        onClick={() => {
                          const ver = previewedVersion ?? previewData.merged_report.current_version;
                          mergedReportsApi.download(
                            previewData.merged_report.id,
                            `Merged_Report_${previewData.merged_report.zone_name}_v${ver}.xlsx`,
                            ver
                          );
                        }}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-[#173042] hover:bg-slate-100"
                      >
                        <Download className="h-3.5 w-3.5 text-[#075D6B]" />
                        Download Excel
                      </button>

                      {isAdmin &&
                        (previewedVersion == null ||
                          previewedVersion === previewData.merged_report.current_version) &&
                        previewData.merged_report.status !== "published" &&
                        previewData.merged_report.status !== "failed" && (
                          <button
                            type="button"
                            onClick={() => setPublishConfirmId(previewData.merged_report.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-[#18A6A0] px-4 py-2 text-xs font-bold text-white hover:bg-[#0D7780] shadow-sm transition"
                          >
                            <Send className="h-3.5 w-3.5" />
                            Publish to Customer
                          </button>
                        )}
                    </div>
                  </div>

                  {/* 6 Preview Tabs */}
                  <div className="flex overflow-x-auto border-b border-slate-200 bg-white px-4">
                    {[
                      { id: "summary", label: "Processing Summary" },
                      {
                        id: "added",
                        label: `Newly Added LED (${previewData.newly_added_records.length})`,
                      },
                      {
                        id: "existing",
                        label: `Existing Lamp Install (${previewData.existing_lamp_records.length})`,
                      },
                      {
                        id: "skipped",
                        label: `Skipped Existing (${previewData.skipped_existing_records.length})`,
                      },
                      {
                        id: "duplicates",
                        label: `Duplicates (${previewData.duplicate_records.length})`,
                      },
                      {
                        id: "invalid",
                        label: `Invalid / Unknown (${previewData.invalid_records.length + previewData.unknown_lamp_types.length})`,
                      },
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => setActiveTab(tab.id as PreviewTab)}
                        className={`whitespace-nowrap border-b-2 px-4 py-3 text-xs font-semibold transition ${
                          activeTab === tab.id
                            ? "border-[#075D6B] text-[#075D6B]"
                            : "border-transparent text-[#718096] hover:text-[#173042]"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {/* Tab Content */}
                  <div className="p-5">
                    {activeTab !== "summary" && (
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div className="relative flex-1 max-w-sm">
                          <Search className="pointer-events-none absolute left-3 top-2 h-3.5 w-3.5 text-[#718096]" />
                          <input
                            type="text"
                            value={previewSearch}
                            onChange={(e) => setPreviewSearch(e.target.value)}
                            placeholder="Search records in this tab..."
                            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-[#173042] focus:border-[#18A6A0] focus:bg-white focus:outline-none"
                          />
                        </div>
                        {previewSearch.trim() && (
                          <button
                            type="button"
                            onClick={() => setPreviewSearch("")}
                            className="text-xs font-semibold text-[#0D7780] hover:underline"
                          >
                            Clear filter
                          </button>
                        )}
                      </div>
                    )}

                    {activeTab === "summary" && (
                      <div className="space-y-5">
                        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                          {[
                            {
                              label: "Existing Lamp Records",
                              val: previewData.summary.total_lamp_installation_records,
                            },
                            {
                              label: "Total Pole Survey",
                              val: previewData.summary.total_survey_records,
                            },
                            {
                              label: "LED Records Found",
                              val: previewData.summary.total_led_records,
                            },
                            {
                              label: "Unique Eligible LED",
                              val: previewData.summary.unique_eligible_led_records,
                            },
                            {
                              label: "Already Present (Skipped)",
                              val: previewData.summary.existing_records,
                            },
                            {
                              label: "New Records Added",
                              val: previewData.summary.added_records,
                              highlight: true,
                            },
                            {
                              label: "Duplicates Excluded",
                              val: previewData.summary.duplicate_records,
                            },
                            {
                              label: "Invalid (Blank Pole)",
                              val: previewData.summary.invalid_records,
                            },
                            {
                              label: "Unknown Lamp Types",
                              val: previewData.summary.unknown_lamp_type_records,
                            },
                            {
                              label: "Final Merged Total",
                              val: previewData.summary.final_merged_records,
                              highlight: true,
                            },
                          ].map((kpi) => (
                            <div
                              key={kpi.label}
                              className={`rounded-xl border p-3.5 ${
                                kpi.highlight
                                  ? "border-teal-200 bg-teal-50/60"
                                  : "border-slate-200 bg-slate-50/50"
                              }`}
                            >
                              <p className="text-[11px] font-semibold text-[#718096]">
                                {kpi.label}
                              </p>
                              <p className="mt-1 text-xl font-bold text-[#173042]">{kpi.val}</p>
                            </div>
                          ))}
                        </div>

                        {previewData.summary.warnings.length > 0 && (
                          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-800 space-y-1">
                            <p className="font-bold">Processing Notes &amp; Warnings</p>
                            {previewData.summary.warnings.map((w, i) => (
                              <p key={i}>• {w}</p>
                            ))}
                          </div>
                        )}

                        {previewData.unknown_lamp_types.length > 0 && (
                          <div className="rounded-xl border border-amber-200 bg-white overflow-hidden">
                            <div className="flex flex-wrap items-center justify-between gap-2 bg-amber-50 px-4 py-2.5 text-xs font-bold text-amber-900">
                              <span>
                                Unknown Lamp Types Requiring Admin Review (Excluded from LED Merge)
                              </span>
                              {isAdmin && (
                                <button
                                  type="button"
                                  onClick={() => navigate("/admin/settings")}
                                  className="rounded-lg border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-[#075D6B] hover:bg-amber-100/50"
                                >
                                  Configure LED Rules
                                </button>
                              )}
                            </div>
                            <div className="max-h-64 overflow-auto">
                              <table className="min-w-full text-left text-xs">
                                <thead className="bg-slate-50 text-[#718096]">
                                  <tr>
                                    <th className="px-4 py-2">Survey Row</th>
                                    <th className="px-4 py-2">Pole Number</th>
                                    <th className="px-4 py-2">Arm Count</th>
                                    <th className="px-4 py-2">Lamp Type</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {previewData.unknown_lamp_types.map((u, i) => (
                                    <tr key={i}>
                                      <td className="px-4 py-2 font-mono">{u.excel_row}</td>
                                      <td className="px-4 py-2 font-semibold">{u.pole_number}</td>
                                      <td className="px-4 py-2">{u.arm_count}</td>
                                      <td className="px-4 py-2 text-amber-700 font-semibold">
                                        {u.lamp_type}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {activeTab === "added" && (() => {
                      const q = previewSearch.trim().toLowerCase();
                      const rows = q
                        ? previewData.newly_added_records.filter((r) =>
                            [r.original_pole_number, r.generated_pole_number, r.lamp_type, r.arm_count]
                              .some((v) => String(v ?? "").toLowerCase().includes(q))
                          )
                        : previewData.newly_added_records;
                      return (
                        <div className="max-h-96 overflow-auto rounded-lg border border-slate-200">
                          {rows.length === 0 ? (
                            <p className="p-6 text-center text-xs text-[#718096]">
                              {previewData.newly_added_records.length === 0
                                ? "All eligible LED poles from Pole Survey already existed in Lamp Installation. Zero new rows added."
                                : "No newly added records match your search."}
                            </p>
                          ) : (
                            <table className="min-w-full text-left text-xs">
                              <thead className="sticky top-0 bg-slate-100 text-[#173042]">
                                <tr>
                                  <th className="px-4 py-2.5">Survey Row</th>
                                  <th className="px-4 py-2.5">Original Pole</th>
                                  <th className="px-4 py-2.5">Generated Pole (Pole Cell)</th>
                                  <th className="px-4 py-2.5">L#</th>
                                  <th className="px-4 py-2.5">Arm Count</th>
                                  <th className="px-4 py-2.5">Lamp Type</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {rows.map((r, idx) => (
                                  <tr key={idx} className="hover:bg-teal-50/40">
                                    <td className="px-4 py-2 font-mono">{r.survey_excel_row}</td>
                                    <td className="px-4 py-2">{r.original_pole_number}</td>
                                    <td className="px-4 py-2 font-bold text-[#075D6B]">
                                      {r.generated_pole_number}
                                    </td>
                                    <td className="px-4 py-2 font-mono">L{r.l_sequence}</td>
                                    <td className="px-4 py-2">{r.arm_count}</td>
                                    <td className="px-4 py-2">{r.lamp_type}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      );
                    })()}

                    {activeTab === "existing" && (() => {
                      const q = previewSearch.trim().toLowerCase();
                      const rows = q
                        ? previewData.existing_lamp_records.filter((row) =>
                            previewData.lamp_columns.some((c) =>
                              String(row[c] ?? "").toLowerCase().includes(q)
                            )
                          )
                        : previewData.existing_lamp_records;
                      return (
                        <div className="max-h-96 overflow-auto rounded-lg border border-slate-200">
                          <table className="min-w-full text-left text-xs">
                            <thead className="sticky top-0 bg-slate-100 text-[#173042]">
                              <tr>
                                <th className="px-3 py-2.5">Row</th>
                                {previewData.lamp_columns.map((c) => (
                                  <th key={c} className="px-3 py-2.5 whitespace-nowrap">
                                    {c}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {rows.slice(0, 200).map((row, idx) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                  <td className="px-3 py-2 font-mono text-[#718096]">
                                    {row._excel_row}
                                  </td>
                                  {previewData.lamp_columns.map((c) => (
                                    <td key={c} className="px-3 py-2 whitespace-nowrap">
                                      {row[c] || <span className="text-slate-300">—</span>}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      );
                    })()}

                    {activeTab === "skipped" && (() => {
                      const q = previewSearch.trim().toLowerCase();
                      const rows = q
                        ? previewData.skipped_existing_records.filter((r) =>
                            [r.original_pole_number, r.lamp_type, r.status]
                              .some((v) => String(v ?? "").toLowerCase().includes(q))
                          )
                        : previewData.skipped_existing_records;
                      return (
                        <div className="max-h-96 overflow-auto rounded-lg border border-slate-200">
                          {rows.length === 0 ? (
                            <p className="p-6 text-center text-xs text-[#718096]">
                              No Pole Survey poles matched existing Lamp Installation poles.
                            </p>
                          ) : (
                            <table className="min-w-full text-left text-xs">
                              <thead className="sticky top-0 bg-slate-100 text-[#173042]">
                                <tr>
                                  <th className="px-4 py-2.5">Survey Row</th>
                                  <th className="px-4 py-2.5">Pole Number</th>
                                  <th className="px-4 py-2.5">Sequence Slot</th>
                                  <th className="px-4 py-2.5">Lamp Type</th>
                                  <th className="px-4 py-2.5">Status</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {rows.map((r, idx) => (
                                  <tr key={idx}>
                                    <td className="px-4 py-2 font-mono">{r.excel_row}</td>
                                    <td className="px-4 py-2 font-semibold">{r.original_pole_number}</td>
                                    <td className="px-4 py-2 font-mono">L{r.l_sequence}</td>
                                    <td className="px-4 py-2">{r.lamp_type}</td>
                                    <td className="px-4 py-2 text-[#718096]">{r.status}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      );
                    })()}

                    {activeTab === "duplicates" && (() => {
                      const q = previewSearch.trim().toLowerCase();
                      const rows = q
                        ? previewData.duplicate_records.filter((r) =>
                            [r.pole_number, r.reason].some((v) =>
                              String(v ?? "").toLowerCase().includes(q)
                            )
                          )
                        : previewData.duplicate_records;
                      return (
                        <div className="max-h-96 overflow-auto rounded-lg border border-slate-200">
                          {rows.length === 0 ? (
                            <p className="p-6 text-center text-xs text-[#718096]">
                              No duplicate Pole Numbers detected in the Pole Survey workbook.
                            </p>
                          ) : (
                            <table className="min-w-full text-left text-xs">
                              <thead className="sticky top-0 bg-slate-100 text-[#173042]">
                                <tr>
                                  <th className="px-4 py-2.5">Duplicate Row</th>
                                  <th className="px-4 py-2.5">Pole Number</th>
                                  <th className="px-4 py-2.5">First Seen Row</th>
                                  <th className="px-4 py-2.5">Reason</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {rows.map((r, idx) => (
                                  <tr key={idx}>
                                    <td className="px-4 py-2 font-mono">{r.excel_row}</td>
                                    <td className="px-4 py-2 font-semibold">{r.pole_number}</td>
                                    <td className="px-4 py-2 font-mono">{r.first_seen_row}</td>
                                    <td className="px-4 py-2 text-[#718096]">{r.reason}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      );
                    })()}

                    {activeTab === "invalid" && (() => {
                      const q = previewSearch.trim().toLowerCase();
                      const invalidRows = q
                        ? previewData.invalid_records.filter((r) =>
                            [r.pole_number, r.lamp_type, r.reason].some((v) =>
                              String(v ?? "").toLowerCase().includes(q)
                            )
                          )
                        : previewData.invalid_records;
                      const unknownRows = q
                        ? previewData.unknown_lamp_types.filter((u) =>
                            [u.pole_number, u.lamp_type, u.reason].some((v) =>
                              String(v ?? "").toLowerCase().includes(q)
                            )
                          )
                        : previewData.unknown_lamp_types;
                      return (
                        <div className="space-y-4">
                          <div className="max-h-64 overflow-auto rounded-lg border border-slate-200">
                            {invalidRows.length === 0 ? (
                              <p className="p-5 text-center text-xs text-[#718096]">
                                No blank/invalid Pole Numbers found.
                              </p>
                            ) : (
                              <table className="min-w-full text-left text-xs">
                                <thead className="sticky top-0 bg-slate-100 text-[#173042]">
                                  <tr>
                                    <th className="px-4 py-2.5">Survey Row</th>
                                    <th className="px-4 py-2.5">Lamp Type</th>
                                    <th className="px-4 py-2.5">Reason</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {invalidRows.map((r, idx) => (
                                    <tr key={idx}>
                                      <td className="px-4 py-2 font-mono">{r.excel_row}</td>
                                      <td className="px-4 py-2">{r.lamp_type}</td>
                                      <td className="px-4 py-2 text-rose-700">{r.reason}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>

                          <div className="rounded-lg border border-amber-200 bg-white overflow-hidden">
                            <div className="flex flex-wrap items-center justify-between gap-2 bg-amber-50 px-4 py-2.5 text-xs font-bold text-amber-900">
                              <span>
                                Unknown Lamp Types ({unknownRows.length}) — Excluded Pending Admin Classification
                              </span>
                              {isAdmin && (
                                <button
                                  type="button"
                                  onClick={() => navigate("/admin/settings")}
                                  className="rounded-lg border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-[#075D6B] hover:bg-amber-100/50"
                                >
                                  Add LED Rule in Settings
                                </button>
                              )}
                            </div>
                            {unknownRows.length === 0 ? (
                              <p className="p-5 text-center text-xs text-[#718096]">
                                No unrecognized lamp types found.
                              </p>
                            ) : (
                              <div className="max-h-64 overflow-auto">
                                <table className="min-w-full text-left text-xs">
                                  <thead className="bg-slate-50 text-[#718096]">
                                    <tr>
                                      <th className="px-4 py-2">Survey Row</th>
                                      <th className="px-4 py-2">Pole Number</th>
                                      <th className="px-4 py-2">Arm Count</th>
                                      <th className="px-4 py-2">Lamp Type</th>
                                      <th className="px-4 py-2">Note</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-100">
                                    {unknownRows.map((u, idx) => (
                                      <tr key={idx}>
                                        <td className="px-4 py-2 font-mono">{u.excel_row}</td>
                                        <td className="px-4 py-2 font-semibold">{u.pole_number}</td>
                                        <td className="px-4 py-2">{u.arm_count}</td>
                                        <td className="px-4 py-2 text-amber-700 font-semibold">
                                          {u.lamp_type}
                                        </td>
                                        <td className="px-4 py-2 text-[#718096]">{u.reason}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Version History inside Preview */}
                  {previewData.merged_report.versions.length > 0 && (
                    <div className="border-t border-slate-100 bg-slate-50/60 px-5 py-3">
                      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#718096]">
                        <History className="h-3.5 w-3.5" /> Generated Merged Versions
                      </p>
                      <div className="space-y-1.5">
                        {previewData.merged_report.versions.map((ver) => (
                          <div
                            key={ver.id}
                            className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white border border-slate-200/70 px-3 py-2 text-xs"
                          >
                            <div className="flex items-center gap-2.5">
                              <span className="font-mono font-bold text-[#075D6B]">
                                v{ver.version}
                              </span>
                              <StatusBadge status={ver.status} />
                              <span className="text-[#718096]">
                                Sources: PS v{ver.source_pole_survey_version} + LI v
                                {ver.source_lamp_installation_version} • {formatBytes(ver.file_size)}
                              </span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-[11px] text-[#718096]">
                                {formatDateTime(ver.generated_at)}
                              </span>
                              <button
                                type="button"
                                onClick={() =>
                                  loadPreview(previewData.merged_report.id, ver.version)
                                }
                                className="font-semibold text-[#0D7780] hover:underline"
                              >
                                Preview
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  mergedReportsApi.download(
                                    previewData.merged_report.id,
                                    `Merged_${previewData.merged_report.zone_name}_v${ver.version}.xlsx`,
                                    ver.version
                                  )
                                }
                                className="font-semibold text-[#075D6B] hover:underline"
                              >
                                Download
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          )}

          {/* Table of Merged Reports */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="text-sm font-bold text-[#173042]">
                {isAdmin ? "All Merged Reports" : "Published Merged Reports"} (
                {visibleReports.length})
              </h2>
            </div>

            {loadingList ? (
              <p className="p-6 text-center text-xs text-[#718096]">Loading Merged Reports...</p>
            ) : visibleReports.length === 0 ? (
              <p className="p-8 text-center text-xs text-[#718096]">
                {isAdmin
                  ? "No Merged Reports generated yet for the selected filter."
                  : "No published Merged Reports are available for this selection yet."}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[#718096]">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Region / Zone</th>
                      <th className="px-4 py-3 font-semibold">Version</th>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-4 py-3 font-semibold">Summary</th>
                      <th className="px-4 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {visibleReports.map((mr) => (
                      <tr key={mr.id} className="hover:bg-slate-50/70">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[#173042]">{mr.zone_name}</p>
                          <p className="text-[11px] text-[#718096]">{mr.region_name}</p>
                        </td>
                        <td className="px-4 py-3 font-mono font-semibold text-[#075D6B]">
                          v{mr.current_version}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={mr.is_outdated ? "outdated" : mr.status} />
                        </td>
                        <td className="px-4 py-3 text-[#718096]">
                          {mr.latest_summary ? (
                            <>
                              <strong className="text-[#075D6B]">
                                +{mr.latest_summary.added_records}
                              </strong>{" "}
                              added / {mr.latest_summary.final_merged_records} total
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="inline-flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => loadPreview(mr.id)}
                              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 font-semibold text-[#173042] hover:bg-slate-100"
                            >
                              <Eye className="h-3 w-3" /> Preview
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                mergedReportsApi.download(
                                  mr.id,
                                  `Merged_${mr.zone_name}_v${mr.current_version}.xlsx`
                                )
                              }
                              className="inline-flex items-center gap-1 rounded-lg bg-[#075D6B] px-2.5 py-1 font-semibold text-white hover:bg-[#0D7780]"
                            >
                              <FileSpreadsheet className="h-3 w-3" /> Download
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

      <ConfirmModal
        open={publishConfirmId !== null}
        title="Publish Merged Report?"
        message="Publishing makes this reconciled Excel workbook and processing summary immediately accessible (read-only) to all Customer users assigned to this region."
        confirmLabel="Publish Report"
        loading={publishing}
        onConfirm={handlePublish}
        onCancel={() => setPublishConfirmId(null)}
      />
    </div>
  );
}
