import React, { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  Lock,
  ShieldCheck,
  User as UserIcon,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { extractErrorMessage } from "../services/api";
import { SchnellLogo } from "../components/common/SchnellLogo";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();

  const [loginType, setLoginType] = useState<"admin" | "customer">("admin");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!identifier.trim()) {
      setError("Please enter your username or email address.");
      return;
    }
    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setSubmitting(true);
    try {
      await login({
        identifier: identifier.trim(),
        password,
        login_type: loginType,
        remember_me: rememberMe,
      });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-[#F4F7F9]">
      {/* Left Brand / Architecture Panel */}
      <div className="hidden lg:flex lg:w-[46%] flex-col justify-between bg-gradient-to-br from-[#075D6B] via-[#075D6B] to-[#0D7780] p-12 text-white relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0 opacity-10"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, #18A6A0 1px, transparent 1px), radial-gradient(circle at 80% 70%, #ffffff 1px, transparent 1px)",
            backgroundSize: "32px 32px",
          }}
        />
        <div className="relative z-10">
          <SchnellLogo />
          <div className="mt-16 max-w-md">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-teal-100 ring-1 ring-white/15">
              <ShieldCheck className="h-3.5 w-3.5 text-[#18A6A0]" />
              Enterprise Utility Asset Portal
            </span>
            <h1 className="mt-5 text-3xl font-extrabold leading-tight tracking-tight">
              Electrical Asset Report Management &amp; LED Reconciliation
            </h1>
            <p className="mt-4 text-sm leading-relaxed text-teal-100/85">
              Centralized region- and zone-wise Excel management for Pole Survey Reports, Lamp
              Installation Master Workbooks, and automated Merged Report generation with
              formatting preservation.
            </p>
          </div>

          <div className="mt-10 space-y-3.5 text-sm text-teal-50/90">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-4 w-4 text-[#18A6A0] shrink-0" />
              <span>Strict zone-isolated Pole Survey &amp; Lamp Installation reconciliation</span>
            </div>
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-4 w-4 text-[#18A6A0] shrink-0" />
              <span>Automated LED detection &amp; deterministic L-number sequencing</span>
            </div>
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-4 w-4 text-[#18A6A0] shrink-0" />
              <span>Full original Excel template formatting &amp; formula preservation</span>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-xs text-teal-200/75">
          © {new Date().getFullYear()} Schnell Energy Equipment Pvt. Ltd. • Asset Report Suite
        </div>
      </div>

      {/* Right Login Card */}
      <div className="flex flex-1 flex-col items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex justify-center lg:hidden">
            <div className="rounded-xl bg-[#075D6B] px-4 py-2.5 shadow-sm">
              <SchnellLogo />
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200/90 bg-white p-8 shadow-elevated">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-[#173042]">Sign In to Dashboard</h2>
              <p className="mt-1 text-xs text-[#718096]">
                Select your portal access mode and enter your credentials
              </p>
            </div>

            {/* Two Login Types: Admin vs Customer */}
            <div className="mt-6 grid grid-cols-2 rounded-xl bg-slate-100 p-1">
              <button
                type="button"
                onClick={() => {
                  setLoginType("admin");
                  setError(null);
                }}
                className={`rounded-lg py-2.5 text-xs font-bold transition ${
                  loginType === "admin"
                    ? "bg-[#075D6B] text-white shadow-sm"
                    : "text-[#718096] hover:text-[#173042]"
                }`}
              >
                Admin Login
              </button>
              <button
                type="button"
                onClick={() => {
                  setLoginType("customer");
                  setError(null);
                }}
                className={`rounded-lg py-2.5 text-xs font-bold transition ${
                  loginType === "customer"
                    ? "bg-[#075D6B] text-white shadow-sm"
                    : "text-[#718096] hover:text-[#173042]"
                }`}
              >
                Customer Login
              </button>
            </div>

            {error && (
              <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-[#173042]">
                  Username or Email
                </label>
                <div className="relative">
                  <UserIcon className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-[#718096]" />
                  <input
                    type="text"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder={
                      loginType === "admin" ? "admin@schnell.local or admin" : "viewer@bbmp.local"
                    }
                    autoComplete="username"
                    className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3.5 text-sm text-[#173042] placeholder:text-slate-400 focus:border-[#18A6A0] focus:outline-none focus:ring-2 focus:ring-[#18A6A0]/20"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold text-[#173042]">
                  Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-[#718096]" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-10 text-sm text-[#173042] placeholder:text-slate-400 focus:border-[#18A6A0] focus:outline-none focus:ring-2 focus:ring-[#18A6A0]/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((s) => !s)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-3 top-2.5 rounded p-0.5 text-[#718096] hover:text-[#173042]"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 text-xs text-[#718096] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-[#075D6B] focus:ring-[#18A6A0]"
                  />
                  Remember me for 7 days
                </label>
                <span className="text-[11px] font-medium text-[#0D7780]">
                  {loginType === "admin" ? "Full Management Access" : "Read-Only Report Access"}
                </span>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="mt-2 w-full rounded-xl bg-[#075D6B] py-3 text-sm font-bold text-white shadow-sm hover:bg-[#0D7780] focus:outline-none focus:ring-2 focus:ring-[#18A6A0] focus:ring-offset-2 disabled:opacity-60 transition"
              >
                {submitting
                  ? "Signing in..."
                  : loginType === "admin"
                  ? "Login as Administrator"
                  : "Login as Customer"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

