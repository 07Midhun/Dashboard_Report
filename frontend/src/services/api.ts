import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000/api";

export const TOKEN_STORAGE_KEY = "schnell_access_token";
export const MERGE_REQUEST_TIMEOUT_MS = 600000;

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || "";
      if (!url.includes("/auth/login")) {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d?.msg || JSON.stringify(d)).join("; ");
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error) return err.message;
  return "An unexpected error occurred.";
}

export async function downloadAuthorizedFile(
  endpointPath: string,
  fallbackFilename: string
): Promise<void> {
  const response = await api.get(endpointPath, {
    responseType: "blob",
    timeout: MERGE_REQUEST_TIMEOUT_MS,
  });
  const disposition = response.headers["content-disposition"] as string | undefined;
  let filename = fallbackFilename;
  if (disposition) {
    const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";\n]+)"?/i);
    if (match?.[1]) {
      filename = decodeURIComponent(match[1]);
    }
  }
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

