import React, { useCallback, useEffect, useState } from "react";
import { Edit3, MapPin, Plus, Power, Trash2 } from "lucide-react";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { hierarchyApi } from "../../services/endpoints";
import type { Customer, Region, Zone } from "../../types";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { StatusBadge } from "../../components/common/StatusBadge";

export function ZonesPage() {
  const { refreshTree } = useHierarchy();
  const { showToast } = useToast();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [selectedCustId, setSelectedCustId] = useState<number | "">("");
  const [selectedRegId, setSelectedRegId] = useState<number | "">("");
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(true);

  const [editing, setEditing] = useState<Zone | null>(null);
  const [editName, setEditName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Zone | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [custList, regList, zoneList] = await Promise.all([
        hierarchyApi.listCustomers(),
        hierarchyApi.listRegions(),
        hierarchyApi.listZones(),
      ]);
      setCustomers(custList);
      setRegions(regList);
      setZones(zoneList);
      if (custList.length > 0 && selectedCustId === "") {
        setSelectedCustId(custList[0].id);
      }
    } catch (err) {
      showToast("error", "Load Failed", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [selectedCustId, showToast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const availableRegions =
    selectedCustId === ""
      ? regions
      : regions.filter((r) => r.customer_id === Number(selectedCustId));

  useEffect(() => {
    if (availableRegions.length > 0 && !availableRegions.some((r) => r.id === selectedRegId)) {
      setSelectedRegId(availableRegions[0].id);
    }
  }, [availableRegions, selectedRegId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRegId || !newName.trim()) return;
    try {
      await hierarchyApi.createZone({
        region_id: Number(selectedRegId),
        zone_name: newName.trim(),
        status: "active",
      });
      setNewName("");
      showToast("success", "Zone Created");
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Create Failed", extractErrorMessage(err));
    }
  };

  const handleSaveEdit = async () => {
    if (!editing || !editName.trim()) return;
    try {
      await hierarchyApi.updateZone(editing.id, { zone_name: editName.trim() });
      setEditing(null);
      showToast("success", "Zone Updated");
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleToggleStatus = async (z: Zone) => {
    const nextStatus = z.status === "active" ? "inactive" : "active";
    try {
      await hierarchyApi.updateZone(z.id, { status: nextStatus });
      showToast("success", "Status Updated", `${z.zone_name} marked ${nextStatus}.`);
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await hierarchyApi.deleteZone(deleteTarget.id);
      showToast("success", "Zone Deleted");
      setDeleteTarget(null);
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Cannot Delete Zone", extractErrorMessage(err));
      setDeleteTarget(null);
    }
  };

  const displayedZones = zones.filter((z) => {
    if (selectedCustId !== "" && z.customer_id !== Number(selectedCustId)) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">Zone Management</h1>
        <p className="mt-1 text-sm text-[#718096]">
          Manage wards and zones under each region. Report processing is strictly isolated per zone.
        </p>
      </div>

      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card flex flex-wrap items-end gap-3"
      >
        <div className="w-full sm:w-52">
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

        <div className="w-full sm:w-52">
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">Region</label>
          <select
            value={selectedRegId}
            onChange={(e) => setSelectedRegId(e.target.value ? Number(e.target.value) : "")}
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-[#173042]"
          >
            {availableRegions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.region_name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1 min-w-[200px]">
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">
            New Zone / Ward Name
          </label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. Indiranagar"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-[#173042]"
          />
        </div>

        <button
          type="submit"
          disabled={!selectedRegId || !newName.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-[#075D6B] px-5 py-2.5 text-xs font-bold text-white hover:bg-[#0D7780] disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Add Zone
        </button>
      </form>

      <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex items-center gap-2">
          <MapPin className="h-4 w-4 text-[#075D6B]" />
          <h2 className="text-sm font-bold text-[#173042]">Zones ({displayedZones.length})</h2>
        </div>

        {loading ? (
          <p className="p-6 text-center text-xs text-[#718096]">Loading zones...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[#718096]">
                <tr>
                  <th className="px-4 py-3 font-semibold">Zone Name</th>
                  <th className="px-4 py-3 font-semibold">Region</th>
                  <th className="px-4 py-3 font-semibold">Report Readiness</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedZones.map((z) => (
                  <tr key={z.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-semibold text-[#173042]">
                      {editing?.id === z.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="rounded-lg border border-teal-300 px-2.5 py-1 text-xs"
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
                        z.zone_name
                      )}
                    </td>
                    <td className="px-4 py-3 text-[#718096]">
                      {z.region_name} ({z.customer_name})
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                            z.has_pole_survey
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          Pole Survey
                        </span>
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-semibold ${
                            z.has_lamp_installation
                              ? "bg-sky-50 text-sky-700 border border-sky-200"
                              : "bg-slate-100 text-slate-500"
                          }`}
                        >
                          Lamp Install
                        </span>
                        {z.merged_status && <StatusBadge status={z.merged_status} />}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={z.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(z);
                            setEditName(z.zone_name);
                          }}
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(z)}
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(z)}
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
        title="Delete Zone?"
        message={`Attempt to delete "${deleteTarget?.zone_name}"? Zones with uploaded or merged reports cannot be deleted and must be deactivated instead.`}
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

