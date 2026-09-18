"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, projectPath, request, toApiError } from "@/lib/api";
import type { Line, Project } from "@/lib/types";

type EtagStyle = "raw" | "quoted" | "weak" | null;

function styleOf(etag: string | null, version: string): EtagStyle {
  if (!etag) return null;
  if (etag === version) return "raw";
  if (etag === `"${version}"`) return "quoted";
  if (etag === `W/"${version}"`) return "weak";
  return null;
}

function etagFor(version: string, style: EtagStyle): string | null {
  if (style === "raw") return version;
  if (style === "quoted") return `"${version}"`;
  if (style === "weak") return `W/"${version}"`;
  return null;
}

function sameLine(a: Line, b: Line): boolean {
  return (
    a.line === b.line &&
    a.number === b.number &&
    a.start === b.start &&
    a.end === b.end &&
    a.text === b.text &&
    a.state === b.state &&
    (a.image?.name ?? null) === (b.image?.name ?? null) &&
    (a.image?.version ?? null) === (b.image?.version ?? null) &&
    (a.image?.thumb ?? null) === (b.image?.thumb ?? null)
  );
}

/**
 * Reuse the previous Line objects wherever nothing changed, so a refetch that
 * only adds a video does not re-render all 170 storyboard rows.
 */
function share(previous: Project | null, next: Project): Project {
  if (!previous || previous.id !== next.id) return next;
  const old = previous.storyboard;
  let changed = old.length !== next.storyboard.length;
  const storyboard = next.storyboard.map((line, index) => {
    const before = old[index];
    if (before && sameLine(before, line)) return before;
    changed = true;
    return line;
  });
  return { ...next, storyboard: changed ? storyboard : old };
}

export type ProjectState = {
  project: Project | null;
  error: ApiError | null;
  loading: boolean;
};

/**
 * One project, fetched on the client. Sends If-None-Match so an unchanged
 * project costs a 304 and no re-render.
 */
export function useProject(id: string) {
  const [state, setState] = useState<ProjectState>({ project: null, error: null, loading: true });
  const etag = useRef<string | null>(null);
  const style = useRef<EtagStyle>(null);

  const refetch = useCallback(async () => {
    try {
      const result = await request<Project>(projectPath(id), { ifNoneMatch: etag.current });
      if (result.status === 304 || !result.data) {
        setState((current) => (current.error || current.loading ? { ...current, error: null, loading: false } : current));
        return;
      }
      const project = result.data;
      style.current = styleOf(result.etag, project.version) ?? style.current;
      etag.current = result.etag ?? etagFor(project.version, style.current);
      setState((current) => ({ project: share(current.project, project), error: null, loading: false }));
    } catch (error) {
      setState((current) => ({ ...current, error: toApiError(error), loading: false }));
    }
  }, [id]);

  /** Take a project a mutation returned, instead of fetching it again. */
  const setProject = useCallback((project: Project) => {
    etag.current = etagFor(project.version, style.current);
    setState((current) => ({ project: share(current.project, project), error: null, loading: false }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      if (!cancelled) await refetch();
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [refetch]);

  return { ...state, refetch, setProject };
}
