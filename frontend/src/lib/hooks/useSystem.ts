"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, toApiError } from "@/lib/api";
import type { SystemInfo } from "@/lib/types";

type State = {
  system: SystemInfo | null;
  error: ApiError | null;
  loading: boolean;
};

/** What the engine knows about this machine: tools, models and storage. */
export function useSystem(enabled = true) {
  const [state, setState] = useState<State>({ system: null, error: null, loading: enabled });

  const refetch = useCallback(async () => {
    try {
      const system = await api<SystemInfo>("/api/system");
      setState({ system, error: null, loading: false });
    } catch (error) {
      setState((current) => ({ ...current, error: toApiError(error), loading: false }));
    }
  }, []);

  useEffect(() => {
    if (enabled) void refetch();
  }, [enabled, refetch]);

  return { ...state, refetch };
}
