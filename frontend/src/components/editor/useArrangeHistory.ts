"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { post, projectPath, toApiError } from "@/lib/api";
import type { ArrangeBody, ArrangeResult, Project, ProjectEnvelope } from "@/lib/types";
import { explain } from "../studio/useStudioActions";
import { useToast } from "../ui/Toast";

// Undo and redo for arranging, wherever it happens: a drag on the timeline or
// the storyboard, Move to line, or Alt with an arrow. Every POST /arrange in
// the app goes through arrange() here.
//
//   undo  POST /undo {undoId}: the API replays the change's record backwards.
//   redo  the same arrange body again, which on the same folder gives the same
//         result and a new undoId.
//
// The toast after an arrangement offers Undo from the same stack. Requests
// run one at a time, in the order they were asked for, so pressing Ctrl+Z
// three times quickly undoes three changes rather than racing.

type Entry = { body: ArrangeBody; undoId: string; summary: string };
type Stacks = { undo: Entry[]; redo: Entry[] };

/** Errors that say "not now" rather than "never": the entry stays for another try. */
const TRANSIENT = new Set(["locked", "busy", "unreachable", "in_use", "aborted"]);
const LIMIT = 100;

type Options = {
  projectId: string;
  setProject: (project: Project) => void;
};

export type ArrangeHistory = {
  arrange: (body: ArrangeBody) => Promise<void>;
  undo: () => Promise<void>;
  redo: () => Promise<void>;
  canUndo: boolean;
  canRedo: boolean;
  /** What undo or redo would change, in the API's words. */
  undoSummary: string | null;
  redoSummary: string | null;
};

export function useArrangeHistory({ projectId, setProject }: Options): ArrangeHistory {
  const { toast } = useToast();
  const [stacks, setStacks] = useState<Stacks>({ undo: [], redo: [] });
  const current = useRef<Stacks>({ undo: [], redo: [] });
  const queue = useRef<Promise<void>>(Promise.resolve());
  /** Redo, for the toast that follows an undo, which is made before redo is. */
  const redoRef = useRef<() => Promise<void>>(async () => undefined);
  /**
   * A redone change gets a new undoId. The toast of the first time still
   * holds the old one, so the old one is followed to the new one.
   */
  const renamed = useRef(new Map<string, string>());

  const commit = useCallback((next: Stacks) => {
    current.current = next;
    setStacks(next);
  }, []);

  const enqueue = useCallback((work: () => Promise<void>) => {
    const run = queue.current.then(work, work);
    queue.current = run.catch(() => undefined);
    return run;
  }, []);

  /** Undo one entry: the newest when undoId is null, or the one a toast names. */
  const undoEntry = useCallback(
    (undoId: string | null): Promise<void> =>
      enqueue(async () => {
        const { undo, redo } = current.current;
        let wanted = undoId;
        for (let hops = 0; wanted !== null && renamed.current.has(wanted) && hops < LIMIT; hops += 1) {
          wanted = renamed.current.get(wanted) ?? null;
        }
        const at = wanted === null ? undo.length - 1 : undo.findIndex((entry) => entry.undoId === wanted);
        if (at < 0) {
          if (undoId !== null) toast({ tone: "info", message: "Already undone" });
          return;
        }
        const entry = undo[at];
        const newest = at === undo.length - 1;
        commit({ undo: undo.filter((_, index) => index !== at), redo });
        try {
          const result = await post<ProjectEnvelope>(projectPath(projectId, "undo"), { undoId: entry.undoId });
          setProject(result.project);
          // Undoing an older change out of order leaves the redo stack
          // describing a folder that no longer exists, so it is cleared.
          const after = current.current;
          commit({ undo: after.undo, redo: newest ? [...after.redo, entry] : [] });
          toast({
            tone: "done",
            message: "Undone",
            detail: entry.summary || undefined,
            action: newest ? { label: "Redo", run: () => redoRef.current() } : undefined,
          });
        } catch (error) {
          const apiError = toApiError(error);
          if (TRANSIENT.has(apiError.code)) {
            const after = current.current;
            const undoAgain = [...after.undo];
            undoAgain.splice(Math.min(at, undoAgain.length), 0, entry);
            commit({ undo: undoAgain, redo: after.redo });
          }
          toast({ tone: "error", message: "Could not undo", detail: explain(apiError) });
        }
      }),
    [commit, enqueue, projectId, setProject, toast],
  );

  const redoEntry = useCallback(
    (): Promise<void> =>
      enqueue(async () => {
        const { redo } = current.current;
        const entry = redo[redo.length - 1];
        if (!entry) return;
        try {
          const result = await post<ArrangeResult>(projectPath(projectId, "arrange"), entry.body);
          setProject(result.project);
          const summary = result.summary || entry.summary;
          const after = current.current;
          const again: Entry = { body: entry.body, undoId: result.undoId, summary };
          if (result.undoId) renamed.current.set(entry.undoId, result.undoId);
          commit({ undo: [...after.undo, again].slice(-LIMIT), redo: after.redo.slice(0, -1) });
          toast({
            tone: "done",
            message: "Redone",
            detail: summary || undefined,
            action: { label: "Undo", run: () => undoEntry(result.undoId) },
          });
        } catch (error) {
          const apiError = toApiError(error);
          if (!TRANSIENT.has(apiError.code)) {
            const after = current.current;
            commit({ undo: after.undo, redo: after.redo.slice(0, -1) });
          }
          toast({ tone: "error", message: "Could not redo", detail: explain(apiError) });
        }
      }),
    [commit, enqueue, projectId, setProject, toast, undoEntry],
  );

  const arrange = useCallback(
    (body: ArrangeBody): Promise<void> =>
      enqueue(async () => {
        try {
          const result = await post<ArrangeResult>(projectPath(projectId, "arrange"), body);
          setProject(result.project);
          if (result.undoId) {
            const after = current.current;
            commit({
              undo: [...after.undo, { body, undoId: result.undoId, summary: result.summary }].slice(-LIMIT),
              redo: [],
            });
          }
          toast({
            tone: "done",
            message: result.summary || "Arranged",
            action: result.undoId ? { label: "Undo", run: () => undoEntry(result.undoId) } : undefined,
          });
        } catch (error) {
          const apiError = toApiError(error);
          if (apiError.code === "aborted") return;
          toast({ tone: "error", message: "Not moved", detail: explain(apiError) });
        }
      }),
    [commit, enqueue, projectId, setProject, toast, undoEntry],
  );

  useEffect(() => {
    redoRef.current = redoEntry;
  }, [redoEntry]);

  const undo = useCallback(() => undoEntry(null), [undoEntry]);

  const undoTop = stacks.undo[stacks.undo.length - 1] ?? null;
  const redoTop = stacks.redo[stacks.redo.length - 1] ?? null;

  return useMemo(
    () => ({
      arrange,
      undo,
      redo: redoEntry,
      canUndo: undoTop !== null,
      canRedo: redoTop !== null,
      undoSummary: undoTop ? undoTop.summary || "the last arrangement" : null,
      redoSummary: redoTop ? redoTop.summary || "the arrangement just undone" : null,
    }),
    [arrange, undo, redoEntry, undoTop, redoTop],
  );
}
