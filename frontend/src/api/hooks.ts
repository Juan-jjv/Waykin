import { useMutation, useQuery } from "@tanstack/react-query";
import { getIncidents, getMeta, planRoutes } from "./client";
import type { RadiusM, RoutesRequest } from "./tmp-types";

export function useMeta() {
  return useQuery({
    queryKey: ["meta"],
    queryFn: getMeta,
    retry: false,
  });
}

export function useIncidents(radiusM: RadiusM, categories: string[], enabled: boolean) {
  return useQuery({
    queryKey: ["incidents", radiusM, categories],
    queryFn: () => getIncidents(radiusM, categories),
    enabled,
  });
}

export function usePlanRoutes() {
  return useMutation({
    mutationFn: (request: RoutesRequest) => planRoutes(request),
  });
}
