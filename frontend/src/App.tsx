import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { HierarchyProvider } from "./contexts/HierarchyContext";
import { ToastProvider } from "./contexts/ToastContext";
import { MainLayout } from "./layouts/MainLayout";
import { LoginPage } from "./pages/LoginPage";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import { CustomersPage } from "./pages/admin/CustomersPage";
import { RegionsPage } from "./pages/admin/RegionsPage";
import { ZonesPage } from "./pages/admin/ZonesPage";
import { UsersPage } from "./pages/admin/UsersPage";
import { UploadHistoryPage } from "./pages/admin/UploadHistoryPage";
import { SettingsPage } from "./pages/admin/SettingsPage";
import { CustomerDashboardPage } from "./pages/customer/CustomerDashboardPage";
import { SourceReportPage } from "./pages/reports/SourceReportPage";
import { MergedReportPage } from "./pages/reports/MergedReportPage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F4F7F9] text-sm font-semibold text-[#075D6B]">
        Initializing Schnell Portal...
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user || user.role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}

function RoleDashboard() {
  const { user } = useAuth();
  if (user?.role === "admin") {
    return <AdminDashboardPage />;
  }
  return <CustomerDashboardPage />;
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <HierarchyProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              <Route
                element={
                  <ProtectedRoute>
                    <MainLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<RoleDashboard />} />
                <Route
                  path="/pole-survey"
                  element={<SourceReportPage reportType="pole_survey" />}
                />
                <Route
                  path="/lamp-installation"
                  element={<SourceReportPage reportType="lamp_installation" />}
                />
                <Route path="/merged-reports" element={<MergedReportPage />} />

                {/* Admin Routes */}
                <Route
                  path="/admin/customers"
                  element={
                    <AdminRoute>
                      <CustomersPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/regions"
                  element={
                    <AdminRoute>
                      <RegionsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/zones"
                  element={
                    <AdminRoute>
                      <ZonesPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/upload-history"
                  element={
                    <AdminRoute>
                      <UploadHistoryPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/users"
                  element={
                    <AdminRoute>
                      <UsersPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/admin/settings"
                  element={
                    <AdminRoute>
                      <SettingsPage />
                    </AdminRoute>
                  }
                />
              </Route>

              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </BrowserRouter>
        </HierarchyProvider>
      </AuthProvider>
    </ToastProvider>
  );
}

