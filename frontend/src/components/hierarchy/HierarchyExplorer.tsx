import { useEffect, useMemo, useState } from "react";
import {
  Building2,
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  FolderTree,
  MapPin,
  RefreshCw,
  Search,
} from "lucide-react";
import { useHierarchy } from "../../contexts/HierarchyContext";

export function HierarchyExplorer({
  onZoneSelected,
}: {
  onZoneSelected?: (customerId: number, regionId: number, zoneId: number) => void;
}) {
  const {
    tree,
    loading,
    selection,
    selectedCustomer,
    selectCustomer,
    selectRegion,
    selectZone,
    refreshTree,
  } = useHierarchy();

  const [searchTerm, setSearchTerm] = useState("");
  const [expandedRegionIds, setExpandedRegionIds] = useState<Record<number, boolean>>({});

  // Auto-expand all regions of the selected customer by default
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

  const filteredRegions = useMemo(() => {
    if (!selectedCustomer) return [];
    const q = searchTerm.trim().toLowerCase();
    if (!q) return selectedCustomer.regions;
    return selectedCustomer.regions
      .map((reg) => {
        const regionMatch = reg.region_name.toLowerCase().includes(q);
        const matchingZones = regionMatch
          ? reg.zones
          : reg.zones.filter((z) => z.zone_name.toLowerCase().includes(q));
        return { ...reg, zones: matchingZones };
      })
      .filter((reg) => reg.zones.length > 0 || reg.region_name.toLowerCase().includes(q));
  }, [selectedCustomer, searchTerm]);

  const expandAll = () => {
    if (!selectedCustomer) return;
    const next: Record<number, boolean> = {};
    selectedCustomer.regions.forEach((r) => {
      next[r.id] = true;
    });
    setExpandedRegionIds(next);
  };

  const collapseAll = () => {
    if (!selectedCustomer) return;
    const next: Record<number, boolean> = {};
    selectedCustomer.regions.forEach((r) => {
      next[r.id] = false;
    });
    setExpandedRegionIds(next);
  };

  return (
    <div className="flex flex-col rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
      {/* Header */}
      <div className="border-b border-slate-100 bg-gradient-to-r from-[#075D6B] to-[#0D7780] px-4 py-3 text-white">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FolderTree className="h-4 w-4 text-teal-200" />
            <h3 className="text-sm font-bold tracking-wide">Region & Zone Hierarchy</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={expandAll}
              title="Expand all regions"
              className="rounded-md p-1 text-teal-100 hover:bg-white/15 hover:text-white"
            >
              <ChevronsUpDown className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={collapseAll}
              title="Collapse all regions"
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

      {/* Customer selector */}
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
                {c.customer_name} ({c.zones_count} zones)
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
            placeholder="Search wards or zones..."
            className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-[#173042] placeholder:text-slate-400 focus:border-[#18A6A0] focus:outline-none focus:ring-2 focus:ring-[#18A6A0]/20"
          />
        </div>
      </div>

      {/* Expandable Region -> Zone tree */}
      <div className="max-h-[460px] overflow-y-auto p-2.5 space-y-1.5">
        {!selectedCustomer ? (
          <p className="py-6 text-center text-xs text-[#718096]">Select a customer to view regions.</p>
        ) : filteredRegions.length === 0 ? (
          <p className="py-6 text-center text-xs text-[#718096]">
            No matching regions or zones found.
          </p>
        ) : (
          filteredRegions.map((reg) => {
            const isExpanded = searchTerm.trim() ? true : !!expandedRegionIds[reg.id];
            const isRegionSelected = selection.regionId === reg.id && selection.zoneId === null;

            return (
              <div key={reg.id} className="rounded-lg border border-slate-100 bg-slate-50/40">
                <div
                  className={`flex items-center justify-between rounded-lg px-2.5 py-2 cursor-pointer transition ${
                    isRegionSelected
                      ? "bg-[#075D6B]/10 text-[#075D6B]"
                      : "hover:bg-slate-100/80 text-[#173042]"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedRegionIds((prev) => ({ ...prev, [reg.id]: !isExpanded }))
                    }
                    className="flex flex-1 items-center gap-2 text-left min-w-0"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-[#0D7780]" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-[#718096]" />
                    )}
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        selectRegion(selectedCustomer.id, reg.id);
                      }}
                      className="truncate text-xs font-bold uppercase tracking-wide"
                    >
                      {reg.region_name}
                    </span>
                  </button>
                  <span className="ml-2 shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-[#075D6B] border border-slate-200">
                    {reg.zones.length}
                  </span>
                </div>

                {isExpanded && (
                  <div className="space-y-0.5 px-2 pb-2 pt-0.5">
                    {reg.zones.length === 0 ? (
                      <p className="pl-6 py-1.5 text-[11px] italic text-[#718096]">No zones yet</p>
                    ) : (
                      reg.zones.map((z) => {
                        const isSelected = selection.zoneId === z.id;
                        return (
                          <button
                            key={z.id}
                            type="button"
                            onClick={() => {
                              selectZone(selectedCustomer.id, reg.id, z.id);
                              onZoneSelected?.(selectedCustomer.id, reg.id, z.id);
                            }}
                            className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs transition ${
                              isSelected
                                ? "bg-[#075D6B] text-white font-semibold shadow-sm"
                                : "text-[#173042] hover:bg-teal-50/70"
                            }`}
                          >
                            <span className="flex items-center gap-2 min-w-0">
                              <MapPin
                                className={`h-3.5 w-3.5 shrink-0 ${
                                  isSelected ? "text-teal-200" : "text-[#18A6A0]"
                                }`}
                              />
                              <span className="truncate">{z.zone_name}</span>
                            </span>
                            <span className="ml-2 flex items-center gap-1 shrink-0">
                              <span
                                title={
                                  z.has_pole_survey
                                    ? "Pole Survey uploaded"
                                    : "Pole Survey missing"
                                }
                                className={`h-2 w-2 rounded-full ${
                                  z.has_pole_survey
                                    ? isSelected
                                      ? "bg-emerald-300"
                                      : "bg-emerald-500"
                                    : isSelected
                                    ? "bg-white/30"
                                    : "bg-slate-300"
                                }`}
                              />
                              <span
                                title={
                                  z.has_lamp_installation
                                    ? "Lamp Installation uploaded"
                                    : "Lamp Installation missing"
                                }
                                className={`h-2 w-2 rounded-full ${
                                  z.has_lamp_installation
                                    ? isSelected
                                      ? "bg-sky-300"
                                      : "bg-sky-500"
                                    : isSelected
                                    ? "bg-white/30"
                                    : "bg-slate-300"
                                }`}
                              />
                              <span
                                title={
                                  z.merged_status === "published"
                                    ? "Merged Report Published"
                                    : z.merged_status
                                    ? `Merged Report: ${z.merged_status}`
                                    : "Merged Report not generated"
                                }
                                className={`h-2 w-2 rounded-full ${
                                  z.merged_status === "published"
                                    ? "bg-[#18A6A0]"
                                    : z.merged_status === "outdated"
                                    ? "bg-amber-400"
                                    : z.merged_status === "draft"
                                    ? "bg-indigo-400"
                                    : isSelected
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

