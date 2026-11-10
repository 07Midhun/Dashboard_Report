import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  FolderTree,
  Layers,
  MapPin,
  RefreshCw,
  Search,
} from "lucide-react";
import { useHierarchy } from "../../contexts/HierarchyContext";

export function HierarchyExplorer({
  onWardSelected,
}: {
  onWardSelected?: (
    customerId: number,
    regionId: number,
    zoneId: number,
    wardId: number
  ) => void;
}) {
  const {
    tree,
    loading,
    selection,
    selectedCustomer,
    selectCustomer,
    selectRegion,
    selectZone,
    selectWard,
    refreshTree,
  } = useHierarchy();

  const [searchTerm, setSearchTerm] = useState("");
  const [expandedRegionIds, setExpandedRegionIds] = useState<Record<number, boolean>>({});
  const [expandedZoneIds, setExpandedZoneIds] = useState<Record<number, boolean>>({});

  // Auto-expand regions of selected customer by default
  useEffect(() => {
    if (!selectedCustomer) return;
    setExpandedRegionIds((prev) => {
      const next = { ...prev };
      for (const reg of selectedCustomer.regions) {
        if (next[reg.id] === undefined) {
          next[reg.id] = true;
        }
      }
      return next;
    });
  }, [selectedCustomer]);

  // Ensure the zone containing the active zone/ward selection is expanded
  useEffect(() => {
    if (selection.zoneId != null) {
      setExpandedZoneIds((prev) => ({ ...prev, [selection.zoneId!]: true }));
    }
    if (selection.regionId != null) {
      setExpandedRegionIds((prev) => ({ ...prev, [selection.regionId!]: true }));
    }
  }, [selection.regionId, selection.zoneId]);

  const filteredRegions = useMemo(() => {
    if (!selectedCustomer) return [];
    const q = searchTerm.trim().toLowerCase();
    if (!q) return selectedCustomer.regions;

    return selectedCustomer.regions
      .map((reg) => {
        const regionMatch = reg.region_name.toLowerCase().includes(q);
        if (regionMatch) {
          return reg;
        }
        const matchingZones = reg.zones
          .map((z) => {
            const zoneMatch =
              z.zone_name.toLowerCase().includes(q) ||
              (z.zone_code ?? "").toLowerCase().includes(q);
            if (zoneMatch) {
              return z;
            }
            const matchingWards = z.wards.filter(
              (w) =>
                w.ward_number.toLowerCase().includes(q) ||
                w.ward_name.toLowerCase().includes(q) ||
                w.ward_code.toLowerCase().includes(q)
            );
            return { ...z, wards: matchingWards };
          })
          .filter(
            (z) =>
              z.wards.length > 0 ||
              z.zone_name.toLowerCase().includes(q) ||
              (z.zone_code ?? "").toLowerCase().includes(q)
          );
        return { ...reg, zones: matchingZones };
      })
      .filter((reg) => reg.zones.length > 0 || reg.region_name.toLowerCase().includes(q));
  }, [selectedCustomer, searchTerm]);

  const expandAll = () => {
    if (!selectedCustomer) return;
    const nextReg: Record<number, boolean> = {};
    const nextZones: Record<number, boolean> = {};
    selectedCustomer.regions.forEach((r) => {
      nextReg[r.id] = true;
      r.zones.forEach((z) => {
        nextZones[z.id] = true;
      });
    });
    setExpandedRegionIds(nextReg);
    setExpandedZoneIds(nextZones);
  };

  const collapseAll = () => {
    if (!selectedCustomer) return;
    const nextReg: Record<number, boolean> = {};
    const nextZones: Record<number, boolean> = {};
    selectedCustomer.regions.forEach((r) => {
      nextReg[r.id] = false;
      r.zones.forEach((z) => {
        nextZones[z.id] = false;
      });
    });
    setExpandedRegionIds(nextReg);
    setExpandedZoneIds(nextZones);
  };

  return (
    <div className="flex flex-col rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
      {/* Header */}
      <div className="border-b border-slate-100 bg-gradient-to-r from-[#075D6B] to-[#0D7780] px-4 py-3 text-white">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FolderTree className="h-4 w-4 text-teal-200" />
            <h3 className="text-sm font-bold tracking-wide">Ward Hierarchy Navigator</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={expandAll}
              title="Expand all regions & zones"
              className="rounded-md p-1 text-teal-100 hover:bg-white/15 hover:text-white"
            >
              <ChevronsUpDown className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={collapseAll}
              title="Collapse all regions & zones"
              className="rounded-md p-1 text-teal-100 hover:bg-white/15 hover:text-white"
            >
              <ChevronsDownUp className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => refreshTree()}
              title="Refresh hierarchy"
              className="rounded-md p-1 text-teal-100 hover:bg-white/15 hover:text-white"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Customer selector & search */}
      <div className="border-b border-slate-100 p-3 space-y-2.5 bg-slate-50/60">
        <div>
          <label className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#718096]">
            <Building2 className="h-3.5 w-3.5 text-[#075D6B]" />
            Customer
          </label>
          <select
            value={selection.customerId ?? ""}
            onChange={(e) => selectCustomer(e.target.value ? Number(e.target.value) : null)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-[#173042] focus:border-[#18A6A0] focus:outline-none focus:ring-2 focus:ring-[#18A6A0]/20"
          >
            {tree.length === 0 && <option value="">No customers available</option>}
            {tree.map((c) => (
              <option key={c.id} value={c.id}>
                {c.customer_name} ({c.zones_count} zones • {c.wards_count} wards)
              </option>
            ))}
          </select>
        </div>

        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[#718096]" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search wards (e.g. W108) or zones (e.g. CVRN)..."
            className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-[#173042] placeholder:text-slate-400 focus:border-[#18A6A0] focus:outline-none focus:ring-2 focus:ring-[#18A6A0]/20"
          />
        </div>
      </div>

      {/* Expandable Region -> Zone -> Ward tree */}
      <div className="max-h-[520px] overflow-y-auto p-2.5 space-y-2">
        {!selectedCustomer ? (
          <p className="py-6 text-center text-xs text-[#718096]">
            Select a customer to view regions, zones, and wards.
          </p>
        ) : filteredRegions.length === 0 ? (
          <p className="py-6 text-center text-xs text-[#718096]">
            No matching regions, zones, or wards found.
          </p>
        ) : (
          filteredRegions.map((reg) => {
            const isRegionExpanded = searchTerm.trim() ? true : !!expandedRegionIds[reg.id];
            const isRegionSelected =
              selection.regionId === reg.id &&
              selection.zoneId === null &&
              selection.wardId === null;

            return (
              <div key={reg.id} className="rounded-lg border border-slate-200/80 bg-slate-50/40">
                {/* Region row */}
                <div
                  className={`flex items-center justify-between rounded-lg px-2.5 py-2 transition ${
                    isRegionSelected
                      ? "bg-[#075D6B]/10 text-[#075D6B]"
                      : "hover:bg-slate-100/80 text-[#173042]"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedRegionIds((prev) => ({
                        ...prev,
                        [reg.id]: !isRegionExpanded,
                      }))
                    }
                    className="flex flex-1 items-center gap-1.5 text-left min-w-0"
                  >
                    {isRegionExpanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-[#0D7780]" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-[#718096]" />
                    )}
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedRegionIds((prev) => ({ ...prev, [reg.id]: true }));
                        selectRegion(selectedCustomer.id, reg.id);
                      }}
                      className="truncate text-xs font-bold uppercase tracking-wide cursor-pointer hover:text-[#075D6B]"
                    >
                      {reg.region_name}
                    </span>
                  </button>
                  <span
                    title={`${reg.zones.length} zones • ${reg.wards_count} wards`}
                    className="ml-2 shrink-0 rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-[#075D6B] border border-slate-200"
                  >
                    {reg.zones.length}z • {reg.wards_count}w
                  </span>
                </div>

                {/* Zones under region */}
                {isRegionExpanded && (
                  <div className="space-y-1 px-2 pb-2 pt-0.5">
                    {reg.zones.length === 0 ? (
                      <p className="pl-6 py-1.5 text-[11px] italic text-[#718096]">No zones yet</p>
                    ) : (
                      reg.zones.map((z) => {
                        const isZoneExpanded = searchTerm.trim() ? true : !!expandedZoneIds[z.id];
                        const isZoneSelectedOnly =
                          selection.zoneId === z.id && selection.wardId === null;
                        const hasSelectedWardInside =
                          selection.zoneId === z.id && selection.wardId !== null;

                        return (
                          <div
                            key={z.id}
                            className={`rounded-lg border ${
                              hasSelectedWardInside
                                ? "border-[#18A6A0]/50 bg-teal-50/30"
                                : "border-slate-200/70 bg-white"
                            }`}
                          >
                            {/* Zone Header */}
                            <div
                              className={`flex items-center justify-between rounded-lg px-2 py-1.5 transition ${
                                isZoneSelectedOnly
                                  ? "bg-[#0D7780]/15 text-[#075D6B] font-semibold"
                                  : "text-[#173042] hover:bg-slate-50"
                              }`}
                            >
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedZoneIds((prev) => ({
                                    ...prev,
                                    [z.id]: !isZoneExpanded,
                                  }))
                                }
                                className="flex flex-1 items-center gap-1.5 text-left min-w-0"
                              >
                                {isZoneExpanded ? (
                                  <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[#0D7780]" />
                                ) : (
                                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[#718096]" />
                                )}
                                <MapPin className="h-3.5 w-3.5 shrink-0 text-[#18A6A0]" />
                                <span
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setExpandedZoneIds((prev) => ({
                                      ...prev,
                                      [z.id]: true,
                                    }));
                                    selectZone(selectedCustomer.id, reg.id, z.id);
                                  }}
                                  className="truncate text-xs font-semibold cursor-pointer hover:text-[#075D6B]"
                                >
                                  {z.zone_name}
                                  {z.zone_code ? (
                                    <span className="ml-1 font-mono text-[10px] font-bold text-[#718096]">
                                      ({z.zone_code})
                                    </span>
                                  ) : null}
                                </span>
                              </button>
                              <span
                                title={`${z.wards.length} wards (${z.wards_with_merged}/${z.wards_count} merged)`}
                                className="ml-1.5 shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-[#173042]"
                              >
                                {z.wards.length}
                              </span>
                            </div>

                            {/* Wards inside Zone */}
                            {isZoneExpanded && (
                              <div className="space-y-0.5 border-t border-slate-100 px-2 py-1.5">
                                {z.wards.length === 0 ? (
                                  <p className="pl-5 py-1 text-[11px] italic text-[#718096]">
                                    No wards configured
                                  </p>
                                ) : (
                                  z.wards.map((w) => {
                                    const isWardSelected = selection.wardId === w.id;
                                    return (
                                      <button
                                        key={w.id}
                                        type="button"
                                        onClick={() => {
                                          selectWard(selectedCustomer.id, reg.id, z.id, w.id);
                                          onWardSelected?.(
                                            selectedCustomer.id,
                                            reg.id,
                                            z.id,
                                            w.id
                                          );
                                        }}
                                        className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition ${
                                          isWardSelected
                                            ? "bg-[#075D6B] text-white font-semibold shadow-sm"
                                            : "text-[#173042] hover:bg-teal-50/70"
                                        }`}
                                      >
                                        <span className="flex items-center gap-1.5 min-w-0">
                                          <Layers
                                            className={`h-3 w-3 shrink-0 ${
                                              isWardSelected ? "text-teal-200" : "text-[#0D7780]"
                                            }`}
                                          />
                                          <span
                                            className={`font-mono text-[11px] font-bold shrink-0 ${
                                              isWardSelected ? "text-teal-100" : "text-[#075D6B]"
                                            }`}
                                          >
                                            {w.ward_number}
                                          </span>
                                          <span
                                            className={`truncate text-[11px] ${
                                              isWardSelected ? "text-white/90" : "text-[#718096]"
                                            }`}
                                          >
                                            {w.ward_name}
                                          </span>
                                        </span>

                                        {/* Ward-level report readiness dots */}
                                        <span className="ml-2 flex items-center gap-1 shrink-0">
                                          <span
                                            title={
                                              w.has_pole_survey
                                                ? "Pole Survey uploaded"
                                                : "Pole Survey missing"
                                            }
                                            className={`h-2 w-2 rounded-full ${
                                              w.has_pole_survey
                                                ? isWardSelected
                                                  ? "bg-emerald-300"
                                                  : "bg-emerald-500"
                                                : isWardSelected
                                                ? "bg-white/30"
                                                : "bg-slate-300"
                                            }`}
                                          />
                                          <span
                                            title={
                                              w.has_lamp_installation
                                                ? "Lamp Installation uploaded"
                                                : "Lamp Installation missing"
                                            }
                                            className={`h-2 w-2 rounded-full ${
                                              w.has_lamp_installation
                                                ? isWardSelected
                                                  ? "bg-sky-300"
                                                  : "bg-sky-500"
                                                : isWardSelected
                                                ? "bg-white/30"
                                                : "bg-slate-300"
                                            }`}
                                          />
                                          <span
                                            title={
                                              w.merged_status === "published"
                                                ? "Merged Report Published"
                                                : w.merged_status
                                                ? `Merged Report: ${w.merged_status}`
                                                : "Merged Report not generated"
                                            }
                                            className={`h-2 w-2 rounded-full ${
                                              w.merged_status === "published"
                                                ? "bg-[#18A6A0]"
                                                : w.merged_status === "outdated"
                                                ? "bg-amber-400"
                                                : w.merged_status === "draft"
                                                ? "bg-indigo-400"
                                                : isWardSelected
                                                ? "bg-white/30"
                                                : "bg-slate-300"
                                            }`}
                                          />
                                        </span>
                                      </button>
                                    );
                                  })
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Legend */}
      <div className="border-t border-slate-100 bg-slate-50 px-3 py-2 flex flex-wrap items-center gap-3 text-[10px] text-[#718096]">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-emerald-500" /> Pole Survey
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-sky-500" /> Lamp Install
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-[#18A6A0]" /> Published Merge
        </span>
      </div>
    </div>
  );
}
