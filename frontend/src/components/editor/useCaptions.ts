"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { patch, projectPath, toApiError } from "@/lib/api";
import { CAPTION_DEFAULTS, sameCaptions } from "@/lib/captions";
import type { CaptionSettings, Project, ProjectEnvelope } from "@/lib/types";
import { useToast } from "../ui/Toast";

/** How long the slider has to be still before the change is saved. */
const SETTLE = 400;

export type CaptionControl = {
  /** What the editor draws, which is the change as soon as it is made. */
  captions: CaptionSettings;
  /** Change a setting. `settle` waits for a dragging slider to come to rest. */
  change: (changes: Partial<CaptionSettings>, settle?: boolean) => void;
  /** Save now, without waiting: a slider let go of. */
  commit: () => void;
};

/**
 * The caption settings, shown at once and saved a moment later.
 *
 * The draft is what the editor draws, so a slider moves with the hand rather
 * than with the network. A button saves straight away; a slider waits until it
 * stops, so one drag is one PATCH instead of ninety. Only the captions are
 * sent, and the API merges them onto the rest, so a build's own settings are
 * never overwritten by a page that was open while it ran.
 *
 * One save runs at a time and then looks again at what is wanted, rather than
 * each change starting its own. Two PATCHes in flight can land in either
 * order, and the one that lands last wins, which is how a slider ends up
 * saved at a value it passed through.
 *
 * A save that fails puts the control back where it was and says so, because a
 * toggle that looks on and is not is worse than one that refuses to move.
 */
export function useCaptions(
  project: Project,
  onProject: (project: Project) => void,
): CaptionControl {
  const { toast } = useToast();
  const stored = project.settings.captions ?? CAPTION_DEFAULTS;
  const [draft, setDraft] = useState<CaptionSettings>(stored);
  /** The last settings the engine is known to hold, to go back to on a failure. */
  const saved = useRef(stored);
  /** What the engine should end up holding. */
  const wanted = useRef(stored);
  const timer = useRef(0);
  const saving = useRef(false);
  const id = project.id;

  // The project changed under us: a build saved its settings, or another
  // window did. Take those, unless a change of our own is still on its way.
  useEffect(() => {
    if (saving.current || timer.current || sameCaptions(stored, saved.current)) return;
    saved.current = stored;
    wanted.current = stored;
    setDraft(stored);
  }, [stored]);

  const save = useCallback(async () => {
    if (saving.current) return;
    saving.current = true;
    try {
      while (!sameCaptions(wanted.current, saved.current)) {
        const next = wanted.current;
        const result = await patch<ProjectEnvelope>(projectPath(id), {
          settings: { captions: next },
        });
        saved.current = result.project.settings.captions ?? next;
        onProject(result.project);
      }
    } catch (failure) {
      wanted.current = saved.current;
      setDraft(saved.current);
      toast({
        tone: "error",
        message: "Captions not saved",
        detail: toApiError(failure).message,
      });
    } finally {
      saving.current = false;
    }
  }, [id, onProject, toast]);

  const change = useCallback(
    (changes: Partial<CaptionSettings>, settle = false) => {
      wanted.current = { ...wanted.current, ...changes };
      setDraft(wanted.current);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        timer.current = 0;
        void save();
      }, settle ? SETTLE : 0);
    },
    [save],
  );

  const commit = useCallback(() => change({}), [change]);

  useEffect(
    () => () => {
      window.clearTimeout(timer.current);
    },
    [],
  );

  return { captions: draft, change, commit };
}
