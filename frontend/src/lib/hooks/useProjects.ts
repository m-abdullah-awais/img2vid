"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, toApiError } from "@/lib/api";
import type { ProjectSummary } from "@/lib/types";

type State = {
  projects: ProjectSummary[] | null;
  error: ApiError | null;
  loading: boolean;
};

/** Every project, newest change first, as the API orders them. */
export function useProjects() {
  const [state, setState] = useState<State>({ projects: null, error: null, loading: true });

  const refetch = useCallback(async () => {
    try {
      const data = await api<{ projects: ProjectSummary[] }>("/api/projects");
      setState({ projects: data.projects, error: null, loading: false });
    } catch (error) {
      setState((current) => ({ ...current, error: toApiError(error), loading: false }));
    }
  }, []);

  /** Apply a change locally before, or instead of, a refetch. */
  const update = useCallback((change: (projects: ProjectSummary[]) => ProjectSummary[]) => {
    setState((current) => (current.projects ? { ...current, projects: change(current.projects) } : current));
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { ...state, refetch, update };
}
