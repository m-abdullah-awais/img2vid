"use client";

import { useDndMonitor } from "@dnd-kit/core";
import { Pause, Play, Redo2, SkipBack, SkipForward, Undo2 } from "lucide-react";
import { memo, useEffect, useRef } from "react";
import { timecode } from "@/lib/format";
import { Button } from "../ui/Button";
import type { ArrangeHistory } from "./useArrangeHistory";
import type { AudioStatus, Playback } from "./usePlayback";

type Props = {
  playing: boolean;
  status: AudioStatus;
  duration: number;
  line: number | null;
  total: number;
  /** The line on screen has no image. */
  missing: boolean;
  /** Why the narration will not play, when it will not. */
  problem: string | null;
  subscribe: Playback["subscribe"];
  onToggle: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onRetry: (() => void) | null;
  history: Pick<ArrangeHistory, "canUndo" | "canRedo" | "undoSummary" | "redoSummary" | "undo" | "redo">;
  /** Images are locked while a video builds, and so is undoing an arrangement. */
  locked: boolean;
};

const square =
  "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-control)] text-muted hover:bg-graphite hover:text-text disabled:cursor-not-allowed disabled:opacity-45";

/** Play, where the playhead is, line by line, and undo for arranging. */
export const Transport = memo(function Transport({
  playing,
  status,
  duration,
  line,
  total,
  missing,
  problem,
  subscribe,
  onToggle,
  onPrevious,
  onNext,
  onRetry,
  history,
  locked,
}: Props) {
  const now = useRef<HTMLSpanElement>(null);

  // The readout is written straight to the DOM, and only when its tenth changes.
  const readout = !problem;
  useEffect(() => {
    if (!readout) return;
    let shown = "";
    return subscribe((seconds) => {
      const text = timecode(seconds);
      if (text !== shown && now.current) {
        shown = text;
        now.current.textContent = text;
      }
    });
  }, [subscribe, readout]);

  const unavailable = status === "none" || status === "failed";
  const undoLabel = history.undoSummary ? `Undo: ${history.undoSummary}` : "Undo";
  const redoLabel = history.redoSummary ? `Redo: ${history.redoSummary}` : "Redo";

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-hairline px-3 py-2 sm:px-4">
      <button
        type="button"
        onClick={onToggle}
        disabled={unavailable}
        aria-label={playing ? "Pause" : "Play"}
        aria-keyshortcuts="Space"
        title={playing ? "Pause (Space)" : "Play (Space)"}
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-text text-graphite enabled:hover:brightness-110 enabled:active:brightness-95 disabled:cursor-not-allowed disabled:opacity-45"
      >
        {playing ? <Pause size={18} fill="currentColor" aria-hidden /> : <Play size={18} fill="currentColor" aria-hidden className="translate-x-px" />}
      </button>

      {problem ? (
        <p className="flex min-w-0 flex-1 items-center gap-3 text-sm text-muted">
          <span className="min-w-0">{problem}</span>
          {onRetry ? (
            <Button size="sm" variant="secondary" onClick={onRetry}>
              Try again
            </Button>
          ) : null}
        </p>
      ) : (
        <p className="timecode text-base whitespace-nowrap">
          <span ref={now}>{timecode(0)}</span>
          <span className="text-muted"> / {timecode(duration)}</span>
        </p>
      )}

      <div className="flex items-center">
        <button
          type="button"
          className={square}
          onClick={onPrevious}
          disabled={!total || line === 1}
          aria-label="Previous line"
          aria-keyshortcuts="ArrowLeft"
          title="Previous line (Left)"
        >
          <SkipBack size={17} aria-hidden />
        </button>
        <button
          type="button"
          className={square}
          onClick={onNext}
          disabled={!total || line === total}
          aria-label="Next line"
          aria-keyshortcuts="ArrowRight"
          title="Next line (Right)"
        >
          <SkipForward size={17} aria-hidden />
        </button>
      </div>

      <div className="flex items-center">
        <button
          type="button"
          className={square}
          onClick={() => void history.undo()}
          disabled={locked || !history.canUndo}
          aria-label={undoLabel}
          aria-keyshortcuts="Control+Z"
          title={`${undoLabel} (Ctrl+Z)`}
        >
          <Undo2 size={17} aria-hidden />
        </button>
        <button
          type="button"
          className={square}
          onClick={() => void history.redo()}
          disabled={locked || !history.canRedo}
          aria-label={redoLabel}
          aria-keyshortcuts="Control+Shift+Z Control+Y"
          title={`${redoLabel} (Ctrl+Shift+Z)`}
        >
          <Redo2 size={17} aria-hidden />
        </button>
      </div>

      {total ? (
        <p className="timecode ml-auto text-sm whitespace-nowrap">
          <span className={missing ? "text-missing" : "text-text"}>Line {line ?? 1}</span>
          <span className="text-muted"> of {total}</span>
          {missing ? <span className="text-missing">, no image</span> : null}
        </p>
      ) : null}
    </div>
  );
});

/** A key left null is not the editor's right now, and keeps its usual meaning in the page. */
export type EditorKeys = {
  toggle: (() => void) | null;
  previous: (() => void) | null;
  next: (() => void) | null;
  undo: () => void;
  redo: () => void;
  zoomIn: (() => void) | null;
  zoomOut: (() => void) | null;
  start: (() => void) | null;
  end: (() => void) | null;
};

function typing(element: Element | null): boolean {
  if (!(element instanceof HTMLElement)) return false;
  if (element.isContentEditable) return true;
  return Boolean(element.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])"));
}

/** A control reached from the keyboard, where Space belongs to it. */
function keyboardControl(element: Element | null): boolean {
  if (!(element instanceof HTMLElement)) return false;
  if (!element.matches("button, a[href], summary, [role='button'], [role='checkbox'], [role='switch']")) return false;
  return element.matches(":focus-visible");
}

/**
 * The editor's keys, on the whole page: Space plays, Left and Right step a
 * line, Ctrl+Z and Ctrl+Shift+Z or Ctrl+Y undo and redo arranging, + and -
 * zoom, Home and End go to either end. None of them fire while typing, while
 * a dialog is open, or while an image is being moved from the keyboard.
 */
export function useEditorKeys(keys: EditorKeys) {
  const latest = useRef(keys);
  const dragging = useRef(false);
  const swallowSpace = useRef(false);

  useEffect(() => {
    latest.current = keys;
  });

  useDndMonitor({
    onDragStart: () => {
      dragging.current = true;
    },
    onDragEnd: () => {
      dragging.current = false;
    },
    onDragCancel: () => {
      dragging.current = false;
    },
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || dragging.current) return;
      if (document.querySelector("dialog[open]")) return;
      const target = event.target instanceof Element ? event.target : null;
      if (typing(target) || typing(document.activeElement)) return;
      const run = latest.current;
      const command = event.ctrlKey || event.metaKey;

      if (command) {
        if (event.altKey) return;
        const key = event.key.toLowerCase();
        if (key === "z" && !event.shiftKey) {
          event.preventDefault();
          run.undo();
        } else if ((key === "z" && event.shiftKey) || (key === "y" && !event.shiftKey)) {
          event.preventDefault();
          run.redo();
        }
        return;
      }
      if (event.altKey) return;

      const table: Record<string, (() => void) | null> = {
        " ": run.toggle,
        ArrowLeft: run.previous,
        ArrowRight: run.next,
        "+": run.zoomIn,
        "=": run.zoomIn,
        "-": run.zoomOut,
        _: run.zoomOut,
        Home: run.start,
        End: run.end,
      };
      const action = table[event.key];
      if (!action) return;
      if (event.key === " " && keyboardControl(target)) return;
      if (event.shiftKey && event.key.startsWith("Arrow")) return;
      event.preventDefault();
      if (event.key === " ") swallowSpace.current = true;
      action();
    };
    // A button activates on the release of Space; after Space played, it must not click too.
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key === " " && swallowSpace.current) {
        swallowSpace.current = false;
        event.preventDefault();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);
}
