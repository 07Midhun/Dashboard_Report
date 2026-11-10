import React, { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity,
  Building2,
  ChevronRight,
  ClipboardList,
  ExternalLink as ExternalLinkIcon,
  FileSpreadsheet,
  GitMerge,
  History,
  Layers,
  LayoutDashboard,
  Lightbulb,
  LogOut,
  Map,
  MapPin,
  Menu,
  Settings,
  Users,
  X,
  Zap,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useHierarchy } from "../contexts/HierarchyContext";
import { useToast } from "../contexts/ToastContext";
import { externalLinksApi } from "../services/endpoints";
import type { ExternalLink } from "../types";
import { SchnellLogo } from "../components/common/SchnellLogo";

export function MainLayout() {
  const { user, logout } = useAuth();
  const { selectedCustomer, selectedRegion, selectedZone, selectedWard } = useHierarchy();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [externalLinks, setExternalLinks] = useState<ExternalLink[]>([]);

  useEffect(() => {
    const syncLinks = () => {
      externalLinksApi
        .list()
        .then(setExternalLinks)
        .catch(() => {
          // Silently ignore if links endpoint is temporarily unavailable
        });
    };
    syncLinks();

    const onLinksUpdated = (e: Event) => {
      const custom = e as CustomEvent<ExternalLink[]>;
      if (Array.isArray(custom.detail)) {
        setExternalLinks(custom.detail);
      } else {
        syncLinks();
      }
    };
    window.addEventListener("schnell:external-links-updated", onLinksUpdated);
    return () => window.removeEventListener("schnell:external-links-updated", onLinksUpdated);
  }, []);

  const isAdmin = user?.role === "admin";

  const handleExternalClick = (key: "om_dashboard" | "energy_saving_report", fallbackLabel: string) => {
    const match = externalLinks.find((l) => l.link_key === key);
    if (!match || !match.is_enabled || !match.url) {
      showToast(
        "info",
        `${match?.link_name || fallbackLabel} Not Configured`,
        isAdmin
          ? "Configure this external application URL under Settings → External Links."
          : "This external dashboard URL has not been configured by the administrator yet."
      );
      if (isAdmin) {
        navigate("/admin/settings");
      }
      return;
    }
    window.open(match.url, "_blank", "noopener,noreferrer");
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
      isActive
        ? "bg-[#18A6A0] text-white shadow-sm"
        : "text-teal-50/90 hover:bg-white/10 hover:text-white"
    }`;

  const renderNavLinks = () => (
    <div className="flex flex-col gap-6 px-3 py-4">
      {/* Primary Report Modules */}
      <div>
        <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-widest text-teal-200/75">
          Asset Reports
        </p>
        <nav className="space-y-1">
          <NavLink
            to="/dashboard"
            onClick={() => setSidebarOpen(false)}
            className={navItemClass}
          >
            <LayoutDashboard className="h-4 w-4 shrink-0" />
            <span>Dashboard</span>
          </NavLink>
          <NavLink
            to="/pole-survey"
            onClick={() => setSidebarOpen(false)}
            className={navItemClass}
          >
            <ClipboardList className="h-4 w-4 shrink-0" />
            <span>Pole Survey Report</span>
          </NavLink>
          <NavLink
            to="/lamp-installation"
            onClick={() => setSidebarOpen(false)}
            className={navItemClass}
          >
            <Lightbulb className="h-4 w-4 shrink-0" />
            <span>Lamp Installation Report</span>
          </NavLink>
          <NavLink
            to="/merged-reports"
            onClick={() => setSidebarOpen(false)}
            className={navItemClass}
          >
            <GitMerge className="h-4 w-4 shrink-0" />
            <span>Merged Report</span>
          </NavLink>
        </nav>
      </div>

      {/* External Applications */}
      <div>
        <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-widest text-teal-200/75">
          Connected Portals
        </p>
        <div className="space-y-1">
          <button
            type="button"
            onClick={() => {
              setSidebarOpen(false);
              handleExternalClick("om_dashboard", "O&M Dashboard");
            }}
            className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium text-teal-50/90 hover:bg-white/10 hover:text-white transition"
          >
            <span className="flex items-center gap-3">
              <Activity className="h-4 w-4 shrink-0" />
              <span>O&amp;M Dashboard</span>
            </span>
            <ExternalLinkIcon className="h-3.5 w-3.5 text-teal-200/75" />
          </button>
          <button
            type="button"
            onClick={() => {
              setSidebarOpen(false);
              handleExternalClick("energy_saving_report", "Energy Saving Report");
            }}
            className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium text-teal-50/90 hover:bg-white/10 hover:text-white transition"
          >
            <span className="flex items-center gap-3">
              <Zap className="h-4 w-4 shrink-0" />
              <span>Energy Saving Report</span>
            </span>
            <ExternalLinkIcon className="h-3.5 w-3.5 text-teal-200/75" />
          </button>
        </div>
      </div>

      {/* Admin Only Management */}
      {isAdmin && (
        <div>
          <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-widest text-teal-200/75">
            Administration
          </p>
          <nav className="space-y-1">
            <NavLink
              to="/admin/customers"
              onClick={() => setSidebarOpen(false)}
              className={navItemClass}
            >
              <Building2 className="h-4 w-4 shrink-0" />
              <span>Customer Management</span>
            </NavLink>
            <NavLink
              to="/admin/regions"
              onClick={() => setSidebarOpen(false)}
              className={navItemClass}
            >
              <Map className="h-4 w-4 shrink-0" />
              <span>Region Management</span>
            </NavLink>
            <NavLink
              to="/admin/zones"
              onClick={() => setSidebarOpen(false)}
              className={navItemClass}
            >
              <MapPin className="h-4 w-4 shrink-0" />
              <span>Zone Management</span>
            </NavLink>
            <NavLink
              to="/admin/wards"
              onClick={() => setSidebarOpen(false)}
              className={navItemClass}
            >
              <Layers className="h-4 w-4 shrink-0" />
              <span>Ward Management</span>
            </NavLink>
            <NavLink
              to="/admin/upload-history"
              onClick={() => setSidebarOpen(false)}
              className={navItemClass}
            >
              <History className="h-4 w-4 shrink-0" />
              <span>Upload History</span>
            </NavLink>
            <NavLink
              to="/admin/users"
              onClick={() => setSidebarOpen(false)}
              className={navItemClass}
            >
              <Users className="h-4 w-4 shrink-0" />
              <span>User Management</span>
            </NavLink>
            <NavLink
              to="/admin/settings"
              onClick={() => setSidebarOpen(false)}
              className={navItemClass}
            >
              <Settings className="h-4 w-4 shrink-0" />
              <span>Settings</span>
            </NavLink>
          </nav>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col bg-[#F4F7F9]">
      {/* Dark Teal Top Navigation Bar */}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-[#075D6B] px-4 lg:px-6 text-white shadow-sm">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => setSidebarOpen((v) => !v)}
            className="rounded-lg p-2 text-teal-100 hover:bg-white/10 lg:hidden"
            aria-label="Toggle navigation"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <SchnellLogo />

          {/* Active 4-Level Hierarchy Breadcrumb */}
          {selectedCustomer && (
            <div className="hidden md:flex items-center gap-1.5 ml-4 rounded-full bg-white/10 px-3.5 py-1.5 text-xs text-teal-50 truncate">
              <FileSpreadsheet className="h-3.5 w-3.5 text-[#18A6A0] shrink-0" />
              <span className="font-semibold truncate">{selectedCustomer.customer_name}</span>
              {selectedRegion && (
                <>
                  <ChevronRight className="h-3.5 w-3.5 text-teal-200/70 shrink-0" />
                  <span className="font-medium truncate">{selectedRegion.region_name}</span>
                </>
              )}
              {selectedZone && (
                <>
                  <ChevronRight className="h-3.5 w-3.5 text-teal-200/70 shrink-0" />
                  <span
                    className={`truncate ${
                      selectedWard
                        ? "font-medium"
                        : "rounded bg-[#18A6A0] px-1.5 py-0.5 font-semibold text-white"
                    }`}
                  >
                    {selectedZone.zone_name}
                    {selectedZone.zone_code ? ` (${selectedZone.zone_code})` : ""}
                  </span>
                </>
              )}
              {selectedWard && (
                <>
                  <ChevronRight className="h-3.5 w-3.5 text-teal-200/70 shrink-0" />
                  <span className="rounded bg-[#18A6A0] px-2 py-0.5 font-semibold text-white shrink-0">
                    {selectedWard.ward_number} • {selectedWard.ward_name}
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* User profile & logout */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden sm:flex flex-col items-end leading-tight">
            <span className="text-sm font-semibold text-white">{user?.name}</span>
            <span className="text-[11px] font-medium uppercase tracking-wider text-teal-200">
              {isAdmin ? "Administrator" : "Customer Read-Only"}
            </span>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#0D7780] text-sm font-bold text-white ring-1 ring-white/25">
            {user?.name?.charAt(0).toUpperCase() || "S"}
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/20 transition"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </header>

      {/* Main Body: Left Sidebar + Content */}
      <div className="flex flex-1 min-h-0">
        {/* Desktop Sidebar */}
        <aside className="hidden lg:flex w-64 shrink-0 flex-col justify-between bg-[#075D6B] border-r border-white/10 overflow-y-auto">
          {renderNavLinks()}
          <div className="border-t border-white/10 p-4 text-[11px] text-teal-200/75">
            <p className="font-semibold text-white/90">Schnell Asset Platform</p>
            <p className="mt-0.5">Ward-Isolated LED Reconciliation</p>
          </div>
        </aside>

        {/* Mobile Drawer */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-40 flex lg:hidden">
            <div
              className="fixed inset-0 bg-slate-900/50"
              onClick={() => setSidebarOpen(false)}
            />
            <aside className="relative z-50 w-64 bg-[#075D6B] text-white overflow-y-auto">
              <div className="flex h-16 items-center justify-between border-b border-white/10 px-4">
                <SchnellLogo />
                <button
                  type="button"
                  onClick={() => setSidebarOpen(false)}
                  className="rounded-lg p-1.5 text-teal-100 hover:bg-white/10"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              {renderNavLinks()}
            </aside>
          </div>
        )}

        {/* Main Content Viewport */}
        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-7 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
