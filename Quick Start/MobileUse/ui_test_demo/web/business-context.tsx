import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { type NavigateOptions, useLocation, useNavigate } from "react-router";

import { api, setBusinessIdResolver } from "./api/client";
import type { BusinessSpace, BusinessSpaceListResponse } from "./api/types";

const STORAGE_KEY = "mua.currentBusinessId";
const DEFAULT_BUSINESS: BusinessSpace = {
  id: "biz_default",
  name: "默认业务",
  description: null,
  is_default: true,
  task_concurrency_limit: 4,
  archived_at: null,
  created_by: "system",
};

type BusinessContextValue = {
  businesses: BusinessSpace[];
  currentBusiness: BusinessSpace;
  selectedBusinessId: string;
  setCurrentBusinessId: (businessId: string) => void;
  createBusiness: (payload: {
    name: string;
    description?: string | null;
    task_concurrency_limit: number;
    runner_settings?: unknown;
  }) => Promise<BusinessSpace>;
  updateBusiness: (
    businessId: string,
    payload: {
      name?: string;
      description?: string | null;
      task_concurrency_limit?: number;
    },
  ) => Promise<void>;
  archiveBusiness: (businessId: string) => Promise<void>;
  isLoading: boolean;
  businessPath: (path?: string) => string;
};

const BusinessContext = createContext<BusinessContextValue | null>(null);
const BUSINESS_PATH_PATTERN = /^\/biz\/([^/]+)(\/.*)?$/;

export function businessIdFromPath(pathname: string): string | null {
  const match = BUSINESS_PATH_PATTERN.exec(pathname);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

export function appPathFromBusinessPath(pathname: string): string {
  const match = BUSINESS_PATH_PATTERN.exec(pathname);
  if (!match) return pathname === "/" ? "/tasks" : pathname;
  return match[2] && match[2] !== "/" ? match[2] : "/tasks";
}

export function businessPath(businessId: string, path = "/tasks"): string {
  const appPath = appPathFromBusinessPath(path);
  const normalized = appPath.startsWith("/") ? appPath : `/${appPath}`;
  return `/biz/${encodeURIComponent(businessId)}${normalized === "/" ? "/tasks" : normalized}`;
}

export function BusinessProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const urlBusinessId = businessIdFromPath(location.pathname);
  const initializedRef = useRef(false);
  const [selectedId, setSelectedId] = useState(
    () => urlBusinessId || localStorage.getItem(STORAGE_KEY) || DEFAULT_BUSINESS.id,
  );

  const spaces = useQuery({
    queryKey: ["business-spaces"],
    queryFn: () => api.get<BusinessSpaceListResponse>("/business-spaces"),
    retry: false,
  });

  const loadingBusiness =
    selectedId !== DEFAULT_BUSINESS.id && !spaces.data?.items?.length
      ? {
        ...DEFAULT_BUSINESS,
        id: selectedId,
        name: selectedId,
        is_default: false,
      }
      : DEFAULT_BUSINESS;
  const businesses = spaces.data?.items?.length ? spaces.data.items : [loadingBusiness];
  const currentBusiness = (
    businesses.find((item) => item.id === selectedId)
    ?? businesses.find((item) => item.is_default)
    ?? DEFAULT_BUSINESS
  );

  useEffect(() => {
    if (urlBusinessId && urlBusinessId !== selectedId) {
      setSelectedId(urlBusinessId);
      return;
    }
    if (spaces.isLoading) return;
    if (currentBusiness.id !== selectedId) {
      setSelectedId(currentBusiness.id);
      if (urlBusinessId) {
        navigate(
          `${businessPath(currentBusiness.id, location.pathname)}${location.search}${location.hash}`,
          { replace: true },
        );
      }
    }
    if (currentBusiness.id === DEFAULT_BUSINESS.id) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, currentBusiness.id);
    }
  }, [
    currentBusiness.id,
    location.hash,
    location.pathname,
    location.search,
    navigate,
    selectedId,
    spaces.isLoading,
    urlBusinessId,
  ]);

  useLayoutEffect(() => {
    setBusinessIdResolver(() => selectedId);
    return () => setBusinessIdResolver(null);
  }, [selectedId]);

  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true;
      return;
    }
    void queryClient.invalidateQueries({
      predicate: (query) => query.queryKey[0] !== "business-spaces",
    });
  }, [queryClient, selectedId]);

  function setCurrentBusinessId(businessId: string) {
    setSelectedId(businessId);
    if (businessId === DEFAULT_BUSINESS.id) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, businessId);
    }
    navigate(
      `${businessPath(businessId, location.pathname)}${location.search}${location.hash}`,
    );
  }

  const createMutation = useMutation({
    mutationFn: (payload: {
      name: string;
      description?: string | null;
      task_concurrency_limit: number;
      runner_settings?: unknown;
    }) =>
      api.post<BusinessSpace>("/business-spaces", payload),
    onSuccess: (created) => {
      queryClient.setQueryData<BusinessSpaceListResponse>(
        ["business-spaces"],
        (previous) => ({ items: [...(previous?.items ?? businesses), created] }),
      );
      setCurrentBusinessId(created.id);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      businessId,
      payload,
    }: {
      businessId: string;
      payload: {
        name?: string;
        description?: string | null;
        task_concurrency_limit?: number;
      };
    }) => api.patch<BusinessSpace>(`/business-spaces/${businessId}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["business-spaces"] });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: (businessId: string) =>
      api.post<BusinessSpace>(`/business-spaces/${businessId}/archive`),
    onSuccess: (archived) => {
      void queryClient.invalidateQueries({ queryKey: ["business-spaces"] });
      if (archived.id === currentBusiness.id) {
        setCurrentBusinessId(DEFAULT_BUSINESS.id);
      }
    },
  });

  const value = useMemo<BusinessContextValue>(
    () => ({
      businesses,
      currentBusiness,
      selectedBusinessId: selectedId,
      setCurrentBusinessId,
      createBusiness: (payload) => createMutation.mutateAsync(payload),
      updateBusiness: async (businessId, payload) => {
        await updateMutation.mutateAsync({ businessId, payload });
      },
      archiveBusiness: async (businessId) => {
        await archiveMutation.mutateAsync(businessId);
      },
      isLoading: spaces.isLoading,
      businessPath: (path = "/tasks") => businessPath(currentBusiness.id, path),
    }),
    [
      archiveMutation,
      businesses,
      createMutation,
      currentBusiness,
      location.pathname,
      selectedId,
      spaces.isLoading,
      updateMutation,
    ],
  );

  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}

export function useBusinessContext(): BusinessContextValue | null {
  return useContext(BusinessContext);
}

export function useBusinessPath() {
  const context = useBusinessContext();
  return (path = "/tasks") => businessPath(context?.currentBusiness.id ?? DEFAULT_BUSINESS.id, path);
}

export function useBusinessNavigate() {
  const navigate = useNavigate();
  const makeBusinessPath = useBusinessPath();
  return (path: string, options?: NavigateOptions) => {
    navigate(makeBusinessPath(path), options);
  };
}

export function defaultBusiness(): BusinessSpace {
  return DEFAULT_BUSINESS;
}
