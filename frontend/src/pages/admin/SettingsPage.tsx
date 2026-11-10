import React, { useCallback, useEffect, useState } from "react";
import { ExternalLink as ExternalLinkIcon, Lightbulb, Plus, Save, ShieldAlert, Trash2 } from "lucide-react";
import { useToast } from "../../contexts/ToastContext";
import { extractErrorMessage } from "../../services/api";
import { adminApi, externalLinksApi } from "../../services/endpoints";
import type { AuditLogEntry, ExternalLink, LedRule } from "../../types";
import { formatDateTime } from "../../utils/format";
import { StatusBadge } from "../../components/common/StatusBadge";

export function SettingsPage() {
  const { showToast } = useToast();

  const [links, setLinks] = useState<ExternalLink[]>([]);
  const [omUrl, setOmUrl] = useState("");
  const [energyUrl, setEnergyUrl] = useState("");
  const [savingLinks, setSavingLinks] = useState(false);

  const [rules, setRules] = useState<LedRule[]>([]);
  const [pattern, setPattern] = useState("");
  const [matchType, setMatchType] = useState<"contains" | "exact" | "prefix" | "word" | "regex">(
    "contains"
  );
  const [classification, setClassification] = useState<"led" | "non_led">("led");

  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);

  const loadSettings = useCallback(async () => {
    try {
      const [extList, ruleList, logs] = await Promise.all([
        externalLinksApi.list(),
        adminApi.listLedRules(),
        adminApi.listAuditLogs(50),
      ]);
      setLinks(extList);
      setOmUrl(extList.find((l) => l.link_key === "om_dashboard")?.url || "");
      setEnergyUrl(extList.find((l) => l.link_key === "energy_saving_report")?.url || "");
      setRules(ruleList);
      setAuditLogs(logs);
    } catch (err) {
      showToast("error", "Settings Load Failed", extractErrorMessage(err));
    }
  }, [showToast]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleSaveLinks = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingLinks(true);
    try {
      const updated = await externalLinksApi.update([
        { link_key: "om_dashboard", url: omUrl.trim() || "" },
        { link_key: "energy_saving_report", url: energyUrl.trim() || "" },
      ]);
      setLinks(updated);
      showToast(
        "success",
        "External URLs Updated",
        "Sidebar links for O&M Dashboard and Energy Saving Report have been updated."
      );
    } catch (err) {
      showToast("error", "Save Failed", extractErrorMessage(err));
    } finally {
      setSavingLinks(false);
    }
  };

  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pattern.trim()) return;
    try {
      await adminApi.createLedRule({
        pattern: pattern.trim(),
        match_type: matchType,
        classification,
        is_active: true,
      });
      setPattern("");
      showToast("success", "LED Classification Rule Added");
      await loadSettings();
    } catch (err) {
      showToast("error", "Rule Create Failed", extractErrorMessage(err));
    }
  };

  const handleDeleteRule = async (id: number) => {
    try {
      await adminApi.deleteLedRule(id);
      showToast("success", "Rule Removed");
      await loadSettings();
    } catch (err) {
      showToast("error", "Delete Failed", extractErrorMessage(err));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[#173042]">Application Settings</h1>
        <p className="mt-1 text-sm text-[#718096]">
          Configure external application URLs, LED Lamp Type classification rules, and inspect audit logs.
        </p>
      </div>

      {/* External Dashboard Links */}
      <form
        onSubmit={handleSaveLinks}
        className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card space-y-4"
      >
        <div className="flex items-center gap-2 text-sm font-bold text-[#173042]">
          <ExternalLinkIcon className="h-4 w-4 text-[#075D6B]" />
          External Dashboard Links
        </div>
        <p className="text-xs text-[#718096]">
          Configure the target URLs for the sidebar O&amp;M Dashboard and Energy Saving Report links.
        </p>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-[#173042]">
              O&amp;M Dashboard URL
            </label>
            <input
              type="url"
              value={omUrl}
              onChange={(e) => setOmUrl(e.target.value)}
              placeholder="https://om.your-domain.com"
              className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-[#173042]"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-[#173042]">
              Energy Saving Report URL
            </label>
            <input
              type="url"
              value={energyUrl}
              onChange={(e) => setEnergyUrl(e.target.value)}
              placeholder="https://energy.your-domain.com"
              className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-[#173042]"
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-1">
          <span className="text-[11px] text-[#718096]">
            {links.some((l) => l.url)
              ? "Configured URLs open securely in a new tab."
              : "Leave blank until external portal URLs are ready."}
          </span>
          <button
            type="submit"
            disabled={savingLinks}
            className="inline-flex items-center gap-2 rounded-xl bg-[#075D6B] px-5 py-2.5 text-xs font-bold text-white hover:bg-[#0D7780] disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {savingLinks ? "Saving..." : "Save External URLs"}
          </button>
        </div>
      </form>

      {/* LED Classification Rules */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-card space-y-4">
        <div className="flex items-center gap-2 text-sm font-bold text-[#173042]">
          <Lightbulb className="h-4 w-4 text-[#075D6B]" />
          LED Lamp Classification Rules
        </div>
        <p className="text-xs text-[#718096]">
          Add accepted LED naming variations or explicit non-LED exclusions (case-insensitive).
          Unknown lamp types are flagged for review rather than guessed.
        </p>

        <form onSubmit={handleAddRule} className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="mb-1 block text-xs font-semibold text-[#173042]">Pattern</label>
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder="e.g. LED 120W or Solar LED"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-[#173042]"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-[#173042]">Match Type</label>
            <select
              value={matchType}
              onChange={(e) => setMatchType(e.target.value as any)}
              className="rounded-xl border border-slate-200 px-3 py-2 text-xs"
            >
              <option value="contains">Contains</option>
              <option value="word">Whole Word</option>
              <option value="exact">Exact</option>
              <option value="prefix">Starts With</option>
              <option value="regex">Regex</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-[#173042]">Classify As</label>
            <select
              value={classification}
              onChange={(e) => setClassification(e.target.value as "led" | "non_led")}
              className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold"
            >
              <option value="led">Eligible LED</option>
              <option value="non_led">Non-LED (Exclude)</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={!pattern.trim()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#075D6B] px-4 py-2 text-xs font-bold text-white hover:bg-[#0D7780] disabled:opacity-50"
          >
            <Plus className="h-4 w-4" /> Add Rule
          </button>
        </form>

        <div className="max-h-64 overflow-auto rounded-lg border border-slate-200">
          <table className="min-w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 text-[#718096]">
              <tr>
                <th className="px-4 py-2.5 font-semibold">Pattern</th>
                <th className="px-4 py-2.5 font-semibold">Match Type</th>
                <th className="px-4 py-2.5 font-semibold">Classification</th>
                <th className="px-4 py-2.5 font-semibold text-right">Remove</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rules.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-2 font-mono font-semibold text-[#173042]">{r.pattern}</td>
                  <td className="px-4 py-2 text-[#718096]">{r.match_type}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={r.classification} />
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => handleDeleteRule(r.id)}
                      className="rounded p-1 text-rose-600 hover:bg-rose-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Logs */}
      <div className="rounded-xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-[#075D6B]" />
          <h2 className="text-sm font-bold text-[#173042]">Recent System Audit Logs</h2>
        </div>
        <div className="max-h-80 overflow-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="sticky top-0 bg-slate-50 text-[#718096]">
              <tr>
                <th className="px-4 py-2.5 font-semibold">Time</th>
                <th className="px-4 py-2.5 font-semibold">User</th>
                <th className="px-4 py-2.5 font-semibold">Action</th>
                <th className="px-4 py-2.5 font-semibold">Entity</th>
                <th className="px-4 py-2.5 font-semibold">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-2 text-[#718096] whitespace-nowrap">
                    {formatDateTime(log.created_at)}
                  </td>
                  <td className="px-4 py-2 font-medium text-[#173042]">
                    {log.user_name || log.user_email || "System"}
                  </td>
                  <td className="px-4 py-2 font-mono text-[#075D6B]">{log.action}</td>
                  <td className="px-4 py-2 text-[#718096]">
                    {log.entity_type}
                    {log.entity_id ? ` #${log.entity_id}` : ""}
                  </td>
                  <td className="px-4 py-2 text-[11px] text-[#718096] max-w-xs truncate">
                    {log.details ? JSON.stringify(log.details) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

