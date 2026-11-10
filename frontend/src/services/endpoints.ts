import { api, downloadAuthorizedFile } from "./api";
import type {
  AdminDashboardData,
  AuditLogEntry,
  Customer,
  CustomerDashboardData,
  ExcelPreview,
  ExternalLink,
  HierarchyCustomerNode,
  LedRule,
  MappingInput,
  MergedReport,
  MergedReportInspect,
  MergedReportPreview,
  Region,
  ReportFile,
  ReportType,
  TokenResponse,
  UploadHistoryItem,
  User,
  Zone,
} from "../types";

export const authApi = {
  login: async (payload: {
    identifier: string;
    password: string;
    login_type: "admin" | "customer";
    remember_me: boolean;
  }): Promise<TokenResponse> => {
    const { data } = await api.post<TokenResponse>("/auth/login", payload);
    return data;
  },
  logout: async (): Promise<void> => {
    await api.post("/auth/logout");
  },
  me: async (): Promise<User> => {
    const { data } = await api.get<User>("/auth/me");
    return data;
  },
};

export const hierarchyApi = {
  getTree: async (): Promise<HierarchyCustomerNode[]> => {
    const { data } = await api.get<HierarchyCustomerNode[]>("/hierarchy/tree");
    return data;
  },
  listCustomers: async (): Promise<Customer[]> => {
    const { data } = await api.get<Customer[]>("/customers");
    return data;
  },
  createCustomer: async (payload: { customer_name: string; status: string }): Promise<Customer> => {
    const { data } = await api.post<Customer>("/customers", payload);
    return data;
  },
  updateCustomer: async (
    id: number,
    payload: { customer_name?: string; status?: string }
  ): Promise<Customer> => {
    const { data } = await api.put<Customer>(`/customers/${id}`, payload);
    return data;
  },
  deleteCustomer: async (id: number): Promise<void> => {
    await api.delete(`/customers/${id}`);
  },
  listRegions: async (customerId?: number): Promise<Region[]> => {
    const { data } = await api.get<Region[]>("/regions", {
      params: customerId ? { customer_id: customerId } : undefined,
    });
    return data;
  },
  createRegion: async (payload: {
    customer_id: number;
    region_name: string;
    status: string;
  }): Promise<Region> => {
    const { data } = await api.post<Region>("/regions", payload);
    return data;
  },
  updateRegion: async (
    id: number,
    payload: { region_name?: string; status?: string }
  ): Promise<Region> => {
    const { data } = await api.put<Region>(`/regions/${id}`, payload);
    return data;
  },
  deleteRegion: async (id: number): Promise<void> => {
    await api.delete(`/regions/${id}`);
  },
  listZones: async (params?: { region_id?: number; customer_id?: number }): Promise<Zone[]> => {
    const { data } = await api.get<Zone[]>("/zones", { params });
    return data;
  },
  createZone: async (payload: {
    region_id: number;
    zone_name: string;
    status: string;
  }): Promise<Zone> => {
    const { data } = await api.post<Zone>("/zones", payload);
    return data;
  },
  updateZone: async (
    id: number,
    payload: { zone_name?: string; status?: string }
  ): Promise<Zone> => {
    const { data } = await api.put<Zone>(`/zones/${id}`, payload);
    return data;
  },
  deleteZone: async (id: number): Promise<void> => {
    await api.delete(`/zones/${id}`);
  },
};

function reportBasePath(reportType: ReportType): string {
  return reportType === "pole_survey" ? "/pole-survey" : "/lamp-installation";
}

export const reportFilesApi = {
  list: async (
    reportType: ReportType,
    params?: { customer_id?: number; region_id?: number; zone_id?: number }
  ): Promise<ReportFile[]> => {
    const { data } = await api.get<ReportFile[]>(reportBasePath(reportType), { params });
    return data;
  },
  upload: async (
    reportType: ReportType,
    formData: FormData,
    onProgress?: (pct: number) => void
  ): Promise<ReportFile> => {
    const { data } = await api.post<ReportFile>(`${reportBasePath(reportType)}/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (evt) => {
        if (evt.total && onProgress) {
          onProgress(Math.round((evt.loaded * 100) / evt.total));
        }
      },
    });
    return data;
  },
  preview: async (
    reportType: ReportType,
    id: number,
    params?: {
      version?: number;
      sheet_name?: string;
      header_row_index?: number;
      search?: string;
      filter_column?: string;
      filter_value?: string;
      page?: number;
      page_size?: number;
    }
  ): Promise<ExcelPreview> => {
    const { data } = await api.get<ExcelPreview>(`${reportBasePath(reportType)}/${id}/preview`, {
      params,
    });
    return data;
  },
  download: async (
    reportType: ReportType,
    id: number,
    fallbackFilename: string,
    version?: number
  ): Promise<void> => {
    const qs = version ? `?version=${version}` : "";
    await downloadAuthorizedFile(`${reportBasePath(reportType)}/${id}/download${qs}`, fallbackFilename);
  },
  remove: async (reportType: ReportType, id: number): Promise<void> => {
    await api.delete(`${reportBasePath(reportType)}/${id}`);
  },
};

export const mergedReportsApi = {
  inspect: async (params: {
    customer_id: number;
    region_id: number;
    zone_id: number;
    pole_sheet?: string;
    pole_header_row?: number;
    lamp_sheet?: string;
    lamp_header_row?: number;
  }): Promise<MergedReportInspect> => {
    const { data } = await api.get<MergedReportInspect>("/merged-reports/inspect", { params });
    return data;
  },
  generate: async (payload: {
    customer_id: number;
    region_id: number;
    zone_id: number;
    pole_survey_mapping: MappingInput;
    lamp_installation_mapping: MappingInput;
    save_mapping: boolean;
  }): Promise<MergedReportPreview> => {
    const { data } = await api.post<MergedReportPreview>("/merged-reports/generate", payload);
    return data;
  },
  list: async (params?: {
    customer_id?: number;
    region_id?: number;
    zone_id?: number;
  }): Promise<MergedReport[]> => {
    const { data } = await api.get<MergedReport[]>("/merged-reports", { params });
    return data;
  },
  preview: async (id: number, version?: number): Promise<MergedReportPreview> => {
    const { data } = await api.get<MergedReportPreview>(`/merged-reports/${id}/preview`, {
      params: version ? { version } : undefined,
    });
    return data;
  },
  publish: async (id: number): Promise<MergedReport> => {
    const { data } = await api.post<MergedReport>(`/merged-reports/${id}/publish`);
    return data;
  },
  download: async (id: number, fallbackFilename: string, version?: number): Promise<void> => {
    const qs = version ? `?version=${version}` : "";
    await downloadAuthorizedFile(`/merged-reports/${id}/download${qs}`, fallbackFilename);
  },
};

export const dashboardApi = {
  getAdmin: async (): Promise<AdminDashboardData> => {
    const { data } = await api.get<AdminDashboardData>("/dashboard/admin");
    return data;
  },
  getCustomer: async (): Promise<CustomerDashboardData> => {
    const { data } = await api.get<CustomerDashboardData>("/dashboard/customer");
    return data;
  },
};

export const externalLinksApi = {
  list: async (): Promise<ExternalLink[]> => {
    const { data } = await api.get<ExternalLink[]>("/external-links");
    return data;
  },
  update: async (
    links: {
      link_key: "om_dashboard" | "energy_saving_report";
      link_name?: string;
      url?: string | null;
      is_enabled?: boolean;
    }[]
  ): Promise<ExternalLink[]> => {
    const { data } = await api.put<ExternalLink[]>("/external-links", { links });
    return data;
  },
};

export const adminApi = {
  listUsers: async (): Promise<User[]> => {
    const { data } = await api.get<User[]>("/users");
    return data;
  },
  createUser: async (payload: {
    name: string;
    email: string;
    username?: string | null;
    password: string;
    role: "admin" | "customer";
    status: "active" | "inactive";
    customer_ids: number[];
  }): Promise<User> => {
    const { data } = await api.post<User>("/users", payload);
    return data;
  },
  updateUser: async (
    id: number,
    payload: {
      name?: string;
      email?: string;
      username?: string | null;
      password?: string;
      role?: "admin" | "customer";
      status?: "active" | "inactive";
      customer_ids?: number[];
    }
  ): Promise<User> => {
    const { data } = await api.put<User>(`/users/${id}`, payload);
    return data;
  },
  listLedRules: async (): Promise<LedRule[]> => {
    const { data } = await api.get<LedRule[]>("/led-rules");
    return data;
  },
  createLedRule: async (payload: {
    pattern: string;
    match_type: "exact" | "prefix" | "contains" | "word" | "regex";
    classification: "led" | "non_led";
    is_active: boolean;
  }): Promise<LedRule> => {
    const { data } = await api.post<LedRule>("/led-rules", payload);
    return data;
  },
  updateLedRule: async (
    id: number,
    payload: Partial<Omit<LedRule, "id" | "created_at">>
  ): Promise<LedRule> => {
    const { data } = await api.put<LedRule>(`/led-rules/${id}`, payload);
    return data;
  },
  deleteLedRule: async (id: number): Promise<void> => {
    await api.delete(`/led-rules/${id}`);
  },
  listUploadHistory: async (reportType?: ReportType): Promise<UploadHistoryItem[]> => {
    const { data } = await api.get<UploadHistoryItem[]>("/upload-history", {
      params: reportType ? { report_type: reportType } : undefined,
    });
    return data;
  },
  listAuditLogs: async (limit = 100): Promise<AuditLogEntry[]> => {
    const { data } = await api.get<AuditLogEntry[]>("/audit-logs", { params: { limit } });
    return data;
  },
};

