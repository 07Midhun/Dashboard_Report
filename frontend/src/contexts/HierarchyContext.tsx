import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { hierarchyApi } from "../services/endpoints";
import type { HierarchyCustomerNode, HierarchyRegionNode, HierarchyZoneNode } from "../types";
import { useAuth } from "./AuthContext";

interface HierarchySelection {
  customerId: number | null;
  regionId: number | null;
  zoneId: number | null;
}

interface HierarchyContextValue {
  tree: HierarchyCustomerNode[];
  loading: boolean;
  selection: HierarchySelection;
  selectedCustomer: HierarchyCustomerNode | null;
  selectedRegion: HierarchyRegionNode | null;
  selectedZone: HierarchyZoneNode | null;
  selectCustomer: (customerId: number | null) => void;
  selectRegion: (customerId: number, regionId: number) => void;
  selectZone: (customerId: number, regionId: number, zoneId: number) => void;
  clearSelection: () => void;
  refreshTree: () => Promise<void>;
}

const HierarchyContext = createContext<HierarchyContextValue | null>(null);

export function HierarchyProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [tree, setTree] = useState<HierarchyCustomerNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [selection, setSelection] = useState<HierarchySelection>({
    customerId: null,
    regionId: null,
    zoneId: null,
  });

  const refreshTree = useCallback(async () => {
    if (!user) {
      setTree([]);
      return;
    }
    setLoading(true);
    try {
      const data = await hierarchyApi.getTree();
      setTree(data);

      // Keep selection valid or auto-select first customer if none selected
      setSelection((prev) => {
        if (prev.customerId) {
          const c = data.find((item) => item.id === prev.customerId);
          if (c) {
            const r = prev.regionId ? c.regions.find((rg) => rg.id === prev.regionId) : null;
            const z = r && prev.zoneId ? r.zones.find((zn) => zn.id === prev.zoneId) : null;
            return {
              customerId: c.id,
              regionId: r ? r.id : null,
              zoneId: z ? z.id : null,
            };
          }
        }
        if (data.length > 0) {
          const firstC = data[0];
          return {
            customerId: firstC.id,
            regionId: null,
            zoneId: null,
          };
        }
        return { customerId: null, regionId: null, zoneId: null };
      });
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    refreshTree();
  }, [refreshTree]);

  const selectCustomer = useCallback((customerId: number | null) => {
    setSelection({ customerId, regionId: null, zoneId: null });
  }, []);

  const selectRegion = useCallback((customerId: number, regionId: number) => {
    setSelection({ customerId, regionId, zoneId: null });
  }, []);

  const selectZone = useCallback((customerId: number, regionId: number, zoneId: number) => {
    setSelection({ customerId, regionId, zoneId });
  }, []);

  const clearSelection = useCallback(() => {
    setSelection((prev) => ({ customerId: prev.customerId, regionId: null, zoneId: null }));
  }, []);

  const selectedCustomer = tree.find((c) => c.id === selection.customerId) ?? null;
  const selectedRegion =
    selectedCustomer?.regions.find((r) => r.id === selection.regionId) ?? null;
  const selectedZone =
    selectedRegion?.zones.find((z) => z.id === selection.zoneId) ?? null;

  return (
    <HierarchyContext.Provider
      value={{
        tree,
        loading,
        selection,
        selectedCustomer,
        selectedRegion,
        selectedZone,
        selectCustomer,
        selectRegion,
        selectZone,
        clearSelection,
        refreshTree,
      }}
    >
      {children}
    </HierarchyContext.Provider>
  );
}

export function useHierarchy() {
  const ctx = useContext(HierarchyContext);
  if (!ctx) throw new Error("useHierarchy must be used inside HierarchyProvider");
  return ctx;
}

