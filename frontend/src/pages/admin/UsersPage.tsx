import React, { useCallback, useEffect, useState } from "react";
import { Plus, Power, Shield, Users } from "lucide-react";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { adminApi, hierarchyApi } from "../../services/endpoints";
import type { Customer, User } from "../../types";
import { formatDateTime } from "../../utils/format";
import { StatusBadge } from "../../components/common/StatusBadge";

export function UsersPage() {
  const { showToast } = useToast();

  const [users, setUsers] = useState<User[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"customer" | "admin">("customer");
  const [assignedCustomerIds, setAssignedCustomerIds] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editCustomers, setEditCustomers] = useState<number[]>([]);
  const [editPassword, setEditPassword] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [uList, cList] = await Promise.all([
        adminApi.listUsers(),
        hierarchyApi.listCustomers(),
      ]);
      setUsers(uList);
      setCustomers(cList);
      if (cList.length > 0 && assignedCustomerIds.length === 0) {
        setAssignedCustomerIds([cList[0].id]);
      }
    } catch (err) {
      showToast("error", "Failed to load users", extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [assignedCustomerIds.length, showToast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleCustomerSelection = (id: number, current: number[], setter: (v: number[]) => void) => {
    if (current.includes(id)) {
      setter(current.filter((x) => x !== id));
    } else {
      setter([...current, id]);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || password.length < 8) {
      showToast("error", "Validation Error", "Provide name, email, and password (min 8 chars).");
      return;
    }
    setSubmitting(true);
    try {
      await adminApi.createUser({
        name: name.trim(),
        email: email.trim(),
        username: username.trim() || null,
        password,
        role,
        status: "active",
        customer_ids: role === "customer" ? assignedCustomerIds : [],
      });
      setName("");
      setEmail("");
      setUsername("");
      setPassword("");
      showToast("success", "Account Created");
      await loadData();
    } catch (err) {
      showToast("error", "Create Failed", extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (u: User) => {
    const nextStatus = u.status === "active" ? "inactive" : "active";
    try {
      await adminApi.updateUser(u.id, { status: nextStatus });
      showToast("success", "User Updated", `${u.name} marked ${nextStatus}.`);
      await loadData();
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  const handleSaveUserEdit = async () => {
    if (!editingUser) return;
    try {
      await adminApi.updateUser(editingUser.id, {
        customer_ids: editingUser.role === "customer" ? editCustomers : undefined,
        password: editPassword.trim() ? editPassword.trim() : undefined,
      });
      setEditingUser(null);
      setEditPassword("");
      showToast("success", "User Access Updated");
      await loadData();
    } catch (err) {
      showToast("error", "Update Failed", extractErrorMessage(err));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">User Management</h1>
        <p className="mt-1 text-sm text-[#718096]">
          Manage administrator and customer read-only accounts and assign customer access scopes.
        </p>
      </div>

      {/* Create User Form */}
      <form
        onSubmit={handleCreate}
        className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card space-y-4"
      >
        <div className="flex items-center gap-2 text-sm font-bold text-[#173042]">
          <Plus className="h-4 w-4 text-[#075D6B]" />
          Create User Account
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Full Name *"
            className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-[#173042]"
          />
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email Address *"
            className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-[#173042]"
          />
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username (optional)"
            className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-[#173042]"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (min 8 chars) *"
            className="rounded-xl border border-slate-200 px-3 py-2 text-xs text-[#173042]"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "customer" | "admin")}
            className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-[#173042]"
          >
            <option value="customer">Customer (Read-Only)</option>
            <option value="admin">Administrator</option>
          </select>
        </div>

        {role === "customer" && (
          <div>
            <p className="mb-1.5 text-xs font-semibold text-[#718096]">
              Assign Authorized Customers:
            </p>
            <div className="flex flex-wrap gap-2">
              {customers.map((c) => {
                const selected = assignedCustomerIds.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() =>
                      toggleCustomerSelection(c.id, assignedCustomerIds, setAssignedCustomerIds)
                    }
                    className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                      selected
                        ? "border-[#075D6B] bg-[#075D6B] text-white"
                        : "border-slate-200 bg-slate-50 text-[#173042]"
                    }`}
                  >
                    {c.customer_name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-xl bg-[#075D6B] px-5 py-2.5 text-xs font-bold text-white hover:bg-[#0D7780] disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            {submitting ? "Creating..." : "Create Account"}
          </button>
        </div>
      </form>

      {/* Users Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex items-center gap-2">
          <Users className="h-4 w-4 text-[#075D6B]" />
          <h2 className="text-sm font-bold text-[#173042]">Accounts ({users.length})</h2>
        </div>

        {loading ? (
          <p className="p-6 text-center text-xs text-[#718096]">Loading users...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-[#718096]">
                <tr>
                  <th className="px-4 py-3 font-semibold">User</th>
                  <th className="px-4 py-3 font-semibold">Role</th>
                  <th className="px-4 py-3 font-semibold">Assigned Customers</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Last Login</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">
                      <p className="font-semibold text-[#173042]">{u.name}</p>
                      <p className="text-[11px] text-[#718096]">
                        {u.email}
                        {u.username ? ` • @${u.username}` : ""}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={u.role} />
                    </td>
                    <td className="px-4 py-3 text-[#718096]">
                      {u.role === "admin" ? (
                        <span className="inline-flex items-center gap-1 text-[#075D6B] font-semibold">
                          <Shield className="h-3.5 w-3.5" /> All Customers
                        </span>
                      ) : u.assigned_customers.length > 0 ? (
                        u.assigned_customers.map((c) => c.customer_name).join(", ")
                      ) : (
                        <span className="text-rose-600">None Assigned</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={u.status} />
                    </td>
                    <td className="px-4 py-3 text-[#718096]">
                      {formatDateTime(u.last_login_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingUser(u);
                            setEditCustomers(u.assigned_customers.map((c) => c.customer_id));
                            setEditPassword("");
                          }}
                          className="rounded-lg border border-slate-200 px-2.5 py-1 font-semibold text-[#173042] hover:bg-slate-100"
                        >
                          Manage Access
                        </button>
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(u)}
                          title={u.status === "active" ? "Deactivate" : "Activate"}
                          className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-100"
                        >
                          <Power className="h-3.5 w-3.5" />
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

      {/* Edit User Modal */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-elevated space-y-4">
            <h3 className="text-base font-bold text-[#173042]">
              Manage Access — {editingUser.name}
            </h3>

            {editingUser.role === "customer" && (
              <div>
                <p className="mb-2 text-xs font-semibold text-[#718096]">Assigned Customers</p>
                <div className="flex flex-wrap gap-2">
                  {customers.map((c) => {
                    const selected = editCustomers.includes(c.id);
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() =>
                          toggleCustomerSelection(c.id, editCustomers, setEditCustomers)
                        }
                        className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                          selected
                            ? "border-[#075D6B] bg-[#075D6B] text-white"
                            : "border-slate-200 bg-slate-50 text-[#173042]"
                        }`}
                      >
                        {c.customer_name}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div>
              <label className="mb-1 block text-xs font-semibold text-[#718096]">
                Reset Password (leave blank to keep existing)
              </label>
              <input
                type="password"
                value={editPassword}
                onChange={(e) => setEditPassword(e.target.value)}
                placeholder="New password (min 8 chars)"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setEditingUser(null)}
                className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveUserEdit}
                className="rounded-lg bg-[#075D6B] px-4 py-2 text-xs font-bold text-white hover:bg-[#0D7780]"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

