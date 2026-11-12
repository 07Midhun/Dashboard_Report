import React, { useCallback, useEffect, useState } from "react";
import { Edit3, Layers, Plus, Power, Search, Trash2 } from "lucide-react";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { hierarchyApi } from "../../services/endpoints";
import type { Customer, Region, Ward, Zone } from "../../types";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { StatusBadge } from "../../components/common/StatusBadge";

export function WardsPage() {
  const { refreshTree } = useHierarchy();
  const { showToast } = useToast();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);

  const [selectedCustId, setSelectedCustId] = useState<number | "">("");
  const [selectedRegId, setSelectedRegId] = useState<number | "">("");
  const [selectedZoneId, setSelectedZoneId] = useState<number | "">("");
  const [tableZoneFilter, setTableZoneFilter] = useState<number | "">("");
  const [searchQuery, setSearchQuery] = useState("");

  const [wardNumber, setWardNumber] = useState("");
  const [wardName, setWardName] = useState("");
  const [wardCode, setWardCode] = useState("");
  const [loading, setLoading] = useState(true);

  const [editing, setEditing] = useState<Ward | null>(null);
  const [editNumber, setEditNumber] = useState("");
  const [editName, setEditName] = useState("");
  const [editCode, setEditCode] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Ward | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [custList, regList, zoneList, wardList] = await Promise.all([
        hierarchyApi.listCustomers(),
        hierarchyApi.listRegions(),
        hierarchyApi.listZones(),
        hierarchyApi.listWards(),
      ]);
      setCustomers(custList);
      setRegions(regList);
      setZones(zoneList);
      setWards(wardList);
      setSelectedCustId((prev) =>
        prev === "" && custList.length > 0 ? custList[0].id : prev
      );
    } catch (err) {
      showToast("error", "Load Failed", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const availableRegions =
    selectedCustId === ""
      ? regions
      : regions.filter((r) => r.customer_id === Number(selectedCustId));

  useEffect(() => {
    if (
      availableRegions.length > 0 &&
      !availableRegions.some((r) => r.id === selectedRegId)
    ) {
      setSelectedRegId(availableRegions[0].id);
    } else if (availableRegions.length === 0) {
      setSelectedRegId("");
    }
  }, [availableRegions, selectedRegId]);

  const availableZones =
    selectedRegId === ""
      ? availableRegions.length === 0
        ? []
        : zones.filter((z) => availableRegions.some((r) => r.id === z.region_id))
      : zones.filter((z) => z.region_id === Number(selectedRegId));

  useEffect(() => {
    if (
      availableZones.length > 0 &&
      !availableZones.some((z) => z.id === selectedZoneId)
    ) {
      setSelectedZoneId(availableZones[0].id);
    } else if (availableZones.length === 0) {
      setSelectedZoneId("");
    }
    if (
      tableZoneFilter !== "" &&
      !availableZones.some((z) => z.id === tableZoneFilter)
    ) {
      setTableZoneFilter("");
    }
  }, [availableZones, selectedZoneId, tableZoneFilter]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedZoneId || !wardNumber.trim() || !wardName.trim()) return;
    try {
      await hierarchyApi.createWard({
        zone_id: Number(selectedZoneId),
        ward_number: wardNumber.trim(),
        ward_name: wardName.trim(),
        ward_code: wardCode.trim() || null,
        status: "active",
      });
      setWardNumber("");
      setWardName("");
      setWardCode("");
      showToast("success", "Ward Created");
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Create Failed", extractErrorMessage(err));
    }
  };

  const handleSaveEdit = async () => {
    if (!editing || !editNumber.trim() || !editName.trim() || !editCode.trim()) return;
    try {
      await hierarchyApi.updateWard(editing.id, {
        ward_number: editNumber.trim(),
        ward_name: editName.trim(),
        ward_code: editCode.trim(),
      });
      setEditing(null);
      showToast("success", "Ward Updated");
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleToggleStatus = async (w: Ward) => {
    const nextStatus = w.status === "active" ? "inactive" : "active";
    try {
      await hierarchyApi.updateWard(w.id, { status: nextStatus });
      showToast(
        "success",
        "Status Updated",
        `${w.ward_number} (${w.ward_name}) marked ${nextStatus}.`
      );
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await hierarchyApi.deleteWard(deleteTarget.id);
      showToast("success", "Ward Deleted");
      setDeleteTarget(null);
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Cannot Delete Ward", extractErrorMessage(err));
      setDeleteTarget(null);
    }
  };

  const displayedWards = wards.filter((w) => {
    if (selectedCustId !== "" && w.customer_id !== Number(selectedCustId)) return false;
    if (selectedRegId !== "" && w.region_id !== Number(selectedRegId)) return false;
    if (tableZoneFilter !== "" && w.zone_id !== Number(tableZoneFilter)) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      return (
        w.ward_number.toLowerCase().includes(q) ||
        w.ward_name.toLowerCase().includes(q) ||
        w.ward_code.toLowerCase().includes(q) ||
        w.zone_name.toLowerCase().includes(q) ||
        (w.zone_code ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">Ward Management</h1>
        <p className="mt-1 text-sm text-[#718096]">
          Manage wards under each zone. All Pole Survey, Lamp Installation, and Merged Report operations take place at the individual ward level.
        </p>
      </div>

      {/* Add Ward Card */}
      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6 items-end"
      >
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">Customer</label>
          <select
            value={selectedCustId}
            onChange={(e) => setSelectedCustId(e.target.value ? Number(e.target.value) : "")}
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-[#173042]"
          >
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.customer_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">Region</label>
          <select
            value={selectedRegId}
            onChange={(e) => setSelectedRegId(e.target.value ? Number(e.target.value) : "")}
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-[#173042]"
          >
            {availableRegions.length === 0 && <option value="">No regions</option>}
            {availableRegions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.region_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">Target Zone</label>
          <select
            value={selectedZoneId}
            onChange={(e) => setSelectedZoneId(e.target.value ? Number(e.target.value) : "")}
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-[#173042]"
          >
            {availableZones.length === 0 && <option value="">No zones</option>}
            {availableZones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.zone_name} {z.zone_code ? `(${z.zone_code})` : ""}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">Ward Number *</label>
          <input
            type="text"
            value={wardNumber}
            onChange={(e) => setWardNumber(e.target.value)}
            placeholder="e.g. W122"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-[#173042]"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">Ward Name *</label>
          <input
            type="text"
            value={wardName}
            onChange={(e) => setWardName(e.target.value)}
            placeholder="e.g. Ward 122"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-[#173042]"
          />
        </div>

        <div className="flex items-end gap-2">
          <div className="flex-1 min-w-0">
            <label className="mb-1.5 block text-xs font-semibold text-[#173042]">Code</label>
            <input
              type="text"
              value={wardCode}
              onChange={(e) => setWardCode(e.target.value)}
              placeholder="Auto"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-[#173042]"
            />
          </div>
          <button
            type="submit"
            disabled={!selectedZoneId || !wardNumber.trim() || !wardName.trim()}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[#075D6B] px-4 py-2.5 text-xs font-bold text-white hover:bg-[#0D7780] disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Add Ward
          </button>
        </div>
      </form>

      {/* Wards Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#075D6B]" />
            <h2 className="text-sm font-bold text-[#173042]">Wards ({displayedWards.length})</h2>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <select
              value={tableZoneFilter}
              onChange={(e) =>
                setTableZoneFilter(e.target.value ? Number(e.target.value) : "")
              }
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-[#173042]"
            >
              <option value="">All Zones in Region</option>
              {availableZones.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.zone_name} {z.zone_code ? `(${z.zone_code})` : ""}
                </option>
              ))}
            </select>

            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-[#718096]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search ward or zone..."
                className="rounded-xl border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-[#173042] focus:border-[#18A6A0] focus:bg-white focus:outline-none"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <p className="p-6 text-center text-xs text-[#718096]">Loading wards...</p>
        ) : displayedWards.length === 0 ? (
          <p className="p-8 text-center text-xs text-[#718096]">
            No wards found matching the current filter.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[#718096]">
                <tr>
                  <th className="px-4 py-3 font-semibold">Ward Number &amp; Name</th>
                  <th className="px-4 py-3 font-semibold">Ward Code</th>
                  <th className="px-4 py-3 font-semibold">Zone / Region</th>
                  <th className="px-4 py-3 font-semibold">Report Readiness</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedWards.map((w) => (
                  <tr key={w.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-semibold text-[#173042]">
                      {editing?.id === w.id ? (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <input
                            type="text"
                            value={editNumber}
                            onChange={(e) => setEditNumber(e.target.value)}
                            className="w-20 rounded-lg border border-teal-300 px-2 py-1 text-xs font-mono"
                            placeholder="W108"
                          />
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="w-36 rounded-lg border border-teal-300 px-2 py-1 text-xs"
                            placeholder="Ward Name"
                          />
                          <input
                            type="text"
                            value={editCode}
                            onChange={(e) => setEditCode(e.target.value)}
                            className="w-24 rounded-lg border border-teal-300 px-2 py-1 text-xs font-mono"
                            placeholder="Code"
                          />
                          <button
                            type="button"
                            onClick={handleSaveEdit}
                            className="rounded bg-[#075D6B] px-2.5 py-1 text-white font-semibold"
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditing(null)}
                            className="text-slate-500 hover:underline"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-[#075D6B]/10 px-2 py-0.5 font-mono text-[11px] font-bold text-[#075D6B]">
                            {w.ward_number}
                          </span>
                          <span>{w.ward_name}</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-[#718096]">
                      {w.ward_code}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-[#173042]">
                        {w.zone_name}{" "}
                        {w.zone_code ? (
                          <span className="font-mono text-[11px] text-[#075D6B]">
                            ({w.zone_code})
                          </span>
                        ) : null}
                      </p>
                      <p className="text-[11px] text-[#718096]">
                        {w.customer_name} • {w.region_name}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                            w.has_pole_survey
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          Pole Survey
                        </span>
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                            w.has_lamp_installation
                              ? "bg-sky-50 text-sky-700 border border-sky-200"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          Lamp Install
                        </span>
                        {w.merged_status && <StatusBadge status={w.merged_status} />}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={w.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(w);
                            setEditNumber(w.ward_number);
                            setEditName(w.ward_name);
                            setEditCode(w.ward_code);
                          }}
                          title="Edit ward"
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(w)}
                          title={w.status === "active" ? "Deactivate ward" : "Activate ward"}
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(w)}
                          title="Delete ward"
                          className="rounded-lg border border-rose-200 p-1.5 text-rose-600 hover:bg-rose-50"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
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

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete Ward?"
        message={`Attempt to delete "${deleteTarget?.ward_number} (${deleteTarget?.ward_name})"? Wards containing uploaded reports, merged reports, or processing logs cannot be deleted and must be deactivated instead.`}
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

