"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { del, post, projectPath, toApiError, upload, type ApiError } from "@/lib/api";
import type {
  ArrangeBody,
  Blocker,
  ArrangePreview,
  LineImageResult,
  Project,
  ProjectEnvelope,
  RestoreResult,
  TrashResult,
} from "@/lib/types";
import type { ArrangeHistory } from "../editor/useArrangeHistory";
import { useToast } from "../ui/Toast";

type Options = {
  project: Project;
  setProject: (project: Project) => void;
  refetch: () => Promise<void>;
  /** Asked before the first arrangement of a folder paired by position. */
  confirmNumbering: (body: ArrangeBody, preview: ArrangePreview) => void;
  setUpload: (line: number, progress: number | null) => void;
  /** Every POST /arrange goes through it, so each one can be undone and redone. */
  history: ArrangeHistory;
};

/** What went wrong, in the API's own words, with the specifics its details carry. */
export function explain(error: ApiError): string {
  const details = error.details as Record<string, unknown> | null;
  if (error.code === "blocked" && details && Array.isArray(details.blockers) && details.blockers.length) {
    return (details.blockers as Blocker[]).map((blocker) => blocker.message).join(" ");
  }
  if (error.code === "record_mismatch" && details && typeof details.missing === "number") {
    const first = typeof details.first === "string" ? `, starting with ${details.first}` : "";
    return `${error.message} ${details.missing} of ${details.total} files it would move have changed since${first}. Nothing was undone.`;
  }
  return error.message;
}

/**
 * Every change the studio makes, each ending in the project the API sent back
 * and, where the API offers one, an Undo.
 */
export function useStudioActions({ project, setProject, refetch, confirmNumbering, setUpload, history }: Options) {
  const { toast } = useToast();
  const current = useRef(project);
  useEffect(() => {
    current.current = project;
  });

  const id = project.id;

  const fail = useCallback(
    (message: string, error: unknown) => {
      const apiError = toApiError(error);
      if (apiError.code === "aborted") return;
      toast({ tone: "error", message, detail: explain(apiError) });
    },
    [toast],
  );

  const restore = useCallback(
    async (trashId: string, what: string) => {
      try {
        const result = await post<RestoreResult>(`/api/trash/${encodeURIComponent(trashId)}/restore`);
        if (result.project) setProject(result.project);
        else await refetch();
        toast({ tone: "done", message: `Restored ${what}` });
      } catch (error) {
        fail(`${what} was not restored`, error);
      }
    },
    [fail, refetch, setProject, toast],
  );

  const undo = useCallback(
    async (undoId: string) => {
      try {
        const result = await post<ProjectEnvelope>(projectPath(id, "undo"), { undoId });
        setProject(result.project);
        toast({ tone: "done", message: "Undone" });
      } catch (error) {
        fail("Could not undo", error);
      }
    },
    [fail, id, setProject, toast],
  );

  // The arrangement itself, its toast and its Undo live in the history.
  const runArrange = history.arrange;

  const arrange = useCallback(
    async (body: ArrangeBody) => {
      if (current.current.images.mode === "positional") {
        try {
          const preview = await post<ArrangePreview>(projectPath(id, "arrange", "preview"), body);
          if (!preview.allowed) {
            toast({ tone: "attention", message: "Not moved", detail: preview.reason || preview.summary });
            return;
          }
          if (preview.numbersFolder) {
            confirmNumbering(body, preview);
            return;
          }
        } catch (error) {
          fail("Not moved", error);
          return;
        }
      }
      await runArrange(body);
    },
    [confirmNumbering, fail, id, runArrange, toast],
  );

  const uploadToLine = useCallback(
    async (file: File, line: number, insert: boolean) => {
      setUpload(line, 0);
      try {
        const result = await upload<LineImageResult>(projectPath(id, "lines", line, "image"), file, {
          query: { name: file.name, insert: insert ? 1 : undefined },
          onProgress: (fraction) => setUpload(line, fraction),
        });
        setProject(result.project);
        // An insert has an undo record. A plain save is undone by taking the
        // new file away and, when it replaced one, restoring that from the trash.
        const undoIt = result.undoId
          ? () => undo(result.undoId as string)
          : async () => {
              try {
                const removed = await del<TrashResult>(projectPath(id, "images", result.saved));
                setProject(removed.project);
              } catch (error) {
                fail(`${result.saved} was not taken away`, error);
                return;
              }
              if (result.trashId) await restore(result.trashId, "the previous image");
              else toast({ tone: "done", message: "Undone" });
            };
        toast({
          tone: "done",
          message: insert ? `Inserted ${result.saved} on line ${line}` : `Saved ${result.saved} on line ${line}`,
          detail: result.trashId && !insert ? "The image it replaced is in the trash." : undefined,
          action: { label: "Undo", run: undoIt },
        });
      } catch (error) {
        fail(`${file.name} was not added`, error);
      } finally {
        setUpload(line, null);
      }
    },
    [fail, id, restore, setProject, setUpload, toast, undo],
  );

  const removeImage = useCallback(
    async (name: string) => {
      try {
        const result = await del<TrashResult>(projectPath(id, "images", name));
        setProject(result.project);
        toast({
          tone: "info",
          message: `Removed ${name}`,
          action: { label: "Undo", run: () => restore(result.trashId, name) },
        });
      } catch (error) {
        fail(`${name} was not removed`, error);
      }
    },
    [fail, id, restore, setProject, toast],
  );

  const removeAudio = useCallback(
    async (name: string) => {
      try {
        const result = await del<TrashResult>(projectPath(id, "audio", name));
        setProject(result.project);
        toast({
          tone: "info",
          message: `Removed ${name}`,
          action: { label: "Undo", run: () => restore(result.trashId, name) },
        });
      } catch (error) {
        fail(`${name} was not removed`, error);
      }
    },
    [fail, id, restore, setProject, toast],
  );

  const removeVideo = useCallback(
    async (name: string) => {
      try {
        const result = await del<TrashResult>(projectPath(id, "videos", name));
        setProject(result.project);
        toast({
          tone: "info",
          message: `Removed ${name}`,
          action: { label: "Undo", run: () => restore(result.trashId, name) },
        });
      } catch (error) {
        fail(`${name} was not removed`, error);
      }
    },
    [fail, id, restore, setProject, toast],
  );

  return useMemo(
    () => ({ fail, restore, undo, arrange, runArrange, uploadToLine, removeImage, removeAudio, removeVideo }),
    [fail, restore, undo, arrange, runArrange, uploadToLine, removeImage, removeAudio, removeVideo],
  );
}

export type StudioActions = ReturnType<typeof useStudioActions>;
