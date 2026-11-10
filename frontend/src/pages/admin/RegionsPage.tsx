import React, { useCallback, useEffect, useState } from "react";
import { Edit3, Map, Plus, Power, Trash2 } from "lucide-react";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { hierarchyApi } from "../../services/endpoints";
import type { Customer, Region } from "../../types";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { StatusBadge } from "../../components/common/StatusBadge";

export function RegionsPage() {
  const { refreshTree } = useHierarchy();
  const { showToast } = useToast();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [selectedCustId, setSelectedCustId] = useState<number | "">("");
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(true);

  const [editing, setEditing] = useState<Region | null>(null);
  const [editName, setEditName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Region | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [custList, regList] = await Promise.all([
        hierarchyApi.listCustomers(),
        hierarchyApi.listRegions(),
      ]);
      setCustomers(custList);
      setRegions(regList);
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

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCustId || !newName.trim()) return;
    try {
      await hierarchyApi.createRegion({
        customer_id: Number(selectedCustId),
        region_name: newName.trim(),
        status: "active",
      });
      setNewName("");
      showToast("success", "Region Created");
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Create Failed", extractErrorMessage(err));
    }
  };

  const handleSaveEdit = async () => {
    if (!editing || !editName.trim()) return;
    try {
      await hierarchyApi.updateRegion(editing.id, { region_name: editName.trim() });
      setEditing(null);
      showToast("success", "Region Updated");
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleToggleStatus = async (reg: Region) => {
    const nextStatus = reg.status === "active" ? "inactive" : "active";
    try {
      await hierarchyApi.updateRegion(reg.id, { status: nextStatus });
      showToast("success", "Status Updated", `${reg.region_name} marked ${nextStatus}.`);
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await hierarchyApi.deleteRegion(deleteTarget.id);
      showToast("success", "Region Deleted");
      setDeleteTarget(null);
      await Promise.all([loadData(), refreshTree()]);
    } catch (err) {
      showToast("error", "Cannot Delete Region", extractErrorMessage(err));
      setDeleteTarget(null);
    }
  };

  const displayedRegions =
    selectedCustId === ""
      ? regions
      : regions.filter((r) => r.customer_id === Number(selectedCustId));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">Region Management</h1>
        <p className="mt-1 text-sm text-[#718096]">
          Add, rename, activate/deactivate regions under each customer and track zone counts.
        </p>
      </div>

      {/* Add Region Form */}
      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card flex flex-wrap items-end gap-3"
      >
        <div className="w-full sm:w-64">
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

        <div className="flex-1 min-w-[220px]">
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">
            New Region Name
          </label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. SOUTH or MAHADEVAPURA"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-[#173042]"
          />
        </div>

        <button
          type="submit"
          disabled={!selectedCustId || !newName.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-[#075D6B] px-5 py-2.5 text-xs font-bold text-white hover:bg-[#0D7780] disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Add Region
        </button>
      </form>

      {/* Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex items-center gap-2">
          <Map className="h-4 w-4 text-[#075D6B]" />
          <h2 className="text-sm font-bold text-[#173042]">Regions ({displayedRegions.length})</h2>
        </div>

        {loading ? (
          <p className="p-6 text-center text-xs text-[#718096]">Loading regions...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[#718096]">
                <tr>
                  <th className="px-4 py-3 font-semibold">Region Name</th>
                  <th className="px-4 py-3 font-semibold">Customer</th>
                  <th className="px-4 py-3 font-semibold text-center">Zones Count</th>
                  <th className="px-4 py-3 font-semibold text-center">Active Files</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedRegions.map((reg) => (
                  <tr key={reg.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-semibold text-[#173042]">
                      {editing?.id === reg.id ? (
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
                        reg.region_name
                      )}
                    </td>
                    <td className="px-4 py-3 text-[#718096]">{reg.customer_name}</td>
                    <td className="px-4 py-3 text-center font-bold text-[#075D6B]">
                      {reg.zones_count}
                    </td>
                    <td className="px-4 py-3 text-center font-semibold">{reg.report_files_count}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={reg.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(reg);
                            setEditName(reg.region_name);
                          }}
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(reg)}
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(reg)}
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
        title="Delete Region?"
        message={`Attempt to delete "${deleteTarget?.region_name}"? Regions containing zones or uploaded reports cannot be deleted and must be deactivated instead.`}
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

