import React, { useCallback, useEffect, useState } from "react";
import { Building2, Edit3, Plus, Power, Trash2 } from "lucide-react";
import { useHierarchy } from "../../contexts/HierarchyContext";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { hierarchyApi } from "../../services/endpoints";
import type { Customer } from "../../types";
import { formatDateTime } from "../../utils/format";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { StatusBadge } from "../../components/common/StatusBadge";

export function CustomersPage() {
  const { refreshTree } = useHierarchy();
  const { showToast } = useToast();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const [editing, setEditing] = useState<Customer | null>(null);
  const [editName, setEditName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Customer | null>(null);

  const loadCustomers = useCallback(async () => {
    setLoading(true);
    try {
      setCustomers(await hierarchyApi.listCustomers());
    } catch (err) {
      showToast("error", "Load Failed", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadCustomers();
  }, [loadCustomers]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await hierarchyApi.createCustomer({ customer_name: newName.trim(), status: "active" });
      setNewName("");
      showToast("success", "Customer Created", "New customer added to hierarchy.");
      await Promise.all([loadCustomers(), refreshTree()]);
    } catch (err) {
      showToast("error", "Create Failed", extractErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editing || !editName.trim()) return;
    try {
      await hierarchyApi.updateCustomer(editing.id, { customer_name: editName.trim() });
      setEditing(null);
      showToast("success", "Customer Updated");
      await Promise.all([loadCustomers(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleToggleStatus = async (cust: Customer) => {
    const nextStatus = cust.status === "active" ? "inactive" : "active";
    try {
      await hierarchyApi.updateCustomer(cust.id, { status: nextStatus });
      showToast("success", "Status Updated", `${cust.customer_name} marked as ${nextStatus}.`);
      await Promise.all([loadCustomers(), refreshTree()]);
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await hierarchyApi.deleteCustomer(deleteTarget.id);
      showToast("success", "Customer Deleted");
      setDeleteTarget(null);
      await Promise.all([loadCustomers(), refreshTree()]);
    } catch (err) {
      showToast("error", "Cannot Delete Customer", extractErrorMessage(err));
      setDeleteTarget(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">Customer Management</h1>
        <p className="mt-1 text-sm text-[#718096]">
          Create and manage municipal or utility customers at the top of the reporting hierarchy.
        </p>
      </div>

      {/* Add Customer Card */}
      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card flex flex-wrap items-end gap-3"
      >
        <div className="flex-1 min-w-[240px]">
          <label className="mb-1.5 block text-xs font-semibold text-[#173042]">
            New Customer Name
          </label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. Mysore Municipal Corporation"
            className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-[#173042] focus:border-[#18A6A0] focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={creating || !newName.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-[#075D6B] px-5 py-2.5 text-xs font-bold text-white hover:bg-[#0D7780] disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          {creating ? "Adding..." : "Add Customer"}
        </button>
      </form>

      {/* Customers Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex items-center gap-2">
          <Building2 className="h-4 w-4 text-[#075D6B]" />
          <h2 className="text-sm font-bold text-[#173042]">All Customers ({customers.length})</h2>
        </div>
        {loading ? (
          <p className="p-6 text-center text-xs text-[#718096]">Loading customers...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[#718096]">
                <tr>
                  <th className="px-4 py-3 font-semibold">Customer Name</th>
                  <th className="px-4 py-3 font-semibold text-center">Regions</th>
                  <th className="px-4 py-3 font-semibold text-center">Zones</th>
                  <th className="px-4 py-3 font-semibold text-center">Wards</th>
                  <th className="px-4 py-3 font-semibold text-center">Active Files</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Created</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-semibold text-[#173042]">
                      {editing?.id === c.id ? (
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
                        c.customer_name
                      )}
                    </td>
                    <td className="px-4 py-3 text-center font-semibold">{c.regions_count}</td>
                    <td className="px-4 py-3 text-center font-semibold">{c.zones_count}</td>
                    <td className="px-4 py-3 text-center font-semibold text-[#0D7780]">{c.wards_count}</td>
                    <td className="px-4 py-3 text-center font-semibold text-[#075D6B]">
                      {c.report_files_count}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-4 py-3 text-[#718096]">{formatDateTime(c.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(c);
                            setEditName(c.customer_name);
                          }}
                          title="Rename customer"
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(c)}
                          title={c.status === "active" ? "Deactivate" : "Activate"}
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(c)}
                          title="Delete customer"
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
        title="Delete Customer?"
        message={`Attempt to delete "${deleteTarget?.customer_name}"? Deletion is blocked if any regions or uploaded reports exist under this customer.`}
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

