import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { RoutesRequest } from "./types";

export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity, retry: 1 });

export const useIncidents = (radius_m: number, categories: string[], days: number, enabled: boolean) =>
  useQuery({
    queryKey: ["incidents", radius_m, categories, days],
    queryFn: () => api.incidents(radius_m, categories, days),
    enabled,
    placeholderData: (previous) => previous,
  });

export const usePlanRoutes = () => useMutation({ mutationFn: (req: RoutesRequest) => api.routes(req) });
