"use client";

import { useDraggable, useDroppable } from "@dnd-kit/core";
import {
  createContext,
  memo,
  useContext,
  useRef,
  useState,
  type DragEvent,
  type HTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { describeDrop, type DragSource, type DropTarget, type Outcome } from "@/lib/arrange";
import type { Line } from "@/lib/types";

// The drop targets of the storyboard and the timeline. Each is a thin shell
// around content its parent built, so when dnd-kit re-renders the shells as
// the pointer moves from one target to the next, the rows and clips inside
// them are not rendered again.
//
//   storyboard  line:N and cell:N place, gap:N inserts above row N
//   timeline    clip:N places, edge:N inserts at the cut before clip N

export type Board = {
  lines: Line[];
  /** Paired by position: arranging numbers the folder first, and uploads onto a line are refused. */
  positional: boolean;
  locked: boolean;
};

export const BoardContext = createContext<Board>({ lines: [], positional: false, locked: false });

function hasFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

/** What a file dropped from the desktop would do here. */
function describeFile(board: Board, target: DropTarget): Outcome {
  if (board.locked) return { allowed: false, noop: false, label: "Images are locked while the video builds" };
  if (board.positional) {
    return {
      allowed: false,
      noop: false,
      label: "Renumber images first. This folder is paired by position, not by number.",
    };
  }
  if (target.op === "place") {
    const slot = board.lines[target.line - 1];
    return {
      allowed: true,
      noop: false,
      label: slot?.image ? `Replace the image on line ${target.line}` : `Put it on line ${target.line}`,
    };
  }
  return describeDrop(board.lines, { image: "", thumb: "", fromLine: null }, target);
}

/** Native file drops: counts enter and leave so child elements do not make it flicker. */
function useFileDrop(board: Board, target: DropTarget, onFiles?: (files: File[], target: DropTarget) => void) {
  const [over, setOver] = useState(false);
  const depth = useRef(0);
  if (!onFiles) return { over: false, handlers: {} };
  return {
    over,
    handlers: {
      onDragEnter(event: DragEvent) {
        if (!hasFiles(event)) return;
        event.preventDefault();
        depth.current += 1;
        setOver(true);
      },
      onDragOver(event: DragEvent) {
        if (!hasFiles(event)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = describeFile(board, target).allowed ? "copy" : "none";
      },
      onDragLeave(event: DragEvent) {
        if (!hasFiles(event)) return;
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setOver(false);
      },
      onDrop(event: DragEvent) {
        if (!hasFiles(event)) return;
        event.preventDefault();
        event.stopPropagation();
        depth.current = 0;
        setOver(false);
        const files = Array.from(event.dataTransfer.files || []);
        if (files.length && (files.length > 1 || describeFile(board, target).allowed)) onFiles(files, target);
      },
    },
  };
}

function DropLabel({ outcome, placement }: { outcome: Outcome; placement: "row" | "gap" | "cell" }) {
  const position =
    placement === "gap"
      ? "right-2 top-1/2 -translate-y-1/2"
      : placement === "cell"
        ? "inset-x-2 bottom-2"
        : "right-3 top-1/2 -translate-y-1/2";
  return (
    <span
      aria-hidden
      className={`pointer-events-none absolute z-20 max-w-[min(440px,80%)] rounded-[var(--radius-control)] px-2.5 py-1 text-sm font-semibold shadow-[0_6px_20px_rgb(0_0_0/0.45)] ${position} ${
        outcome.allowed ? "bg-text text-graphite" : "border border-hairline bg-graphite text-text"
      }`}
    >
      {outcome.label}
    </span>
  );
}

type ShellProps = Omit<HTMLAttributes<HTMLDivElement>, "children"> & {
  dropId: string;
  target: DropTarget;
  children: ReactNode;
  placement: "row" | "cell";
  onFiles?: (files: File[], target: DropTarget) => void;
};

/** A line as a drop target: place an image here, or drop a file on it. */
export function LineTarget({ dropId, target, children, placement, onFiles, className = "", ...rest }: ShellProps) {
  const board = useContext(BoardContext);
  const { setNodeRef, isOver, active } = useDroppable({ id: dropId, disabled: board.locked });
  const file = useFileDrop(board, target, onFiles);

  let outcome: Outcome | null = null;
  if (isOver && active?.data.current) {
    outcome = describeDrop(board.lines, active.data.current as DragSource, target);
  } else if (file.over) {
    outcome = describeFile(board, target);
  }
  const lit = outcome
    ? outcome.allowed
      ? "bg-panel shadow-[inset_0_0_0_2px_var(--color-text)]"
      : "shadow-[inset_0_0_0_1px_var(--color-muted)]"
    : "";

  return (
    <div ref={setNodeRef} {...file.handlers} {...rest} className={`motion-drop relative ${className} ${lit}`}>
      {children}
      {outcome ? <DropLabel outcome={outcome} placement={placement} /> : null}
    </div>
  );
}

/** The space above a row: insert here, and the lines below move down to the first empty one. */
export function GapTarget({
  line,
  onFiles,
}: {
  line: number;
  onFiles?: (files: File[], target: DropTarget) => void;
}) {
  const board = useContext(BoardContext);
  const target: DropTarget = { op: "insert", line };
  const { setNodeRef, isOver, active } = useDroppable({ id: `gap:${line}`, disabled: board.locked });
  const file = useFileDrop(board, target, onFiles);

  let outcome: Outcome | null = null;
  if (isOver && active?.data.current) {
    outcome = describeDrop(board.lines, active.data.current as DragSource, target);
  } else if (file.over) {
    outcome = describeFile(board, target);
  }

  return (
    <div ref={setNodeRef} {...file.handlers} className="relative h-2.5">
      {outcome ? (
        <>
          <span
            aria-hidden
            className={`absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 ${outcome.allowed ? "bg-text" : "bg-muted"}`}
          />
          <DropLabel outcome={outcome} placement="gap" />
        </>
      ) : null}
    </div>
  );
}

type HandleProps = {
  source: DragSource;
  label: string;
  className?: string;
  onOpen?: () => void;
  children: ReactNode;
};

/** The image itself is what you pick up. A click without moving opens it instead. */
export function DragHandle({ source, label, className = "", onOpen, children }: HandleProps) {
  const board = useContext(BoardContext);
  const { setNodeRef, attributes, listeners, isDragging } = useDraggable({
    id: `img:${source.image}`,
    data: source,
    disabled: board.locked,
  });
  return (
    <button
      ref={setNodeRef}
      type="button"
      {...attributes}
      {...listeners}
      aria-label={label}
      aria-roledescription="draggable image"
      onClick={onOpen}
      className={`relative block cursor-grab touch-manipulation overflow-hidden rounded-[var(--radius-frame)] active:cursor-grabbing disabled:cursor-default ${
        isDragging ? "opacity-35" : ""
      } ${className}`}
    >
      {children}
    </button>
  );
}

// The timeline's shells. Clips are narrow, so what a drop would do is said
// above the clip, over the ruler, rather than on it.

function ClipDropLabel({ outcome }: { outcome: Outcome }) {
  return (
    <span
      aria-hidden
      className={`pointer-events-none absolute bottom-full left-1/2 z-30 mb-1 -translate-x-1/2 rounded-[var(--radius-control)] px-2 py-0.5 text-xs font-semibold whitespace-nowrap shadow-[0_6px_20px_rgb(0_0_0/0.45)] ${
        outcome.allowed ? "bg-text text-graphite" : "border border-hairline bg-graphite text-text"
      }`}
    >
      {outcome.label}
    </span>
  );
}

type ClipTargetProps = {
  line: number;
  left: number;
  width: number;
  selected: boolean;
  onFiles?: (files: File[], target: DropTarget) => void;
  children: ReactNode;
};

/** A clip as a drop target: an image dropped here goes onto its line, and so does a file. */
export function ClipTarget({ line, left, width, selected, onFiles, children }: ClipTargetProps) {
  const board = useContext(BoardContext);
  const target: DropTarget = { op: "place", line };
  const { setNodeRef, isOver, active } = useDroppable({ id: `clip:${line}`, disabled: board.locked });
  const file = useFileDrop(board, target, onFiles);

  let outcome: Outcome | null = null;
  if (isOver && active?.data.current) {
    outcome = describeDrop(board.lines, active.data.current as DragSource, target);
  } else if (file.over) {
    outcome = describeFile(board, target);
  }

  return (
    <div
      ref={setNodeRef}
      {...file.handlers}
      data-clip={line}
      style={{ left, width }}
      className={`absolute inset-y-1 ${selected || outcome ? "z-10" : ""} ${
        // Outside the frame, past a graphite gap, so it reads against light and dark pictures alike.
        selected ? "shadow-[0_0_0_1px_var(--color-graphite),0_0_0_3px_var(--color-text)]" : ""
      }`}
    >
      {children}
      {outcome ? (
        <>
          <span
            aria-hidden
            className={`pointer-events-none absolute inset-0 ${
              outcome.allowed ? "bg-text/15 shadow-[inset_0_0_0_2px_var(--color-text)]" : "shadow-[inset_0_0_0_1px_var(--color-muted)]"
            }`}
          />
          <ClipDropLabel outcome={outcome} />
        </>
      ) : null}
    </div>
  );
}

/**
 * The cut before clip `line`: drop an image here to insert it, and the lines
 * after it move along to the first empty one. It takes no pointer events, so
 * a click near a cut still reaches the clip; dnd-kit finds it by its box.
 */
export const EdgeTarget = memo(function EdgeTarget({ line, left, width }: { line: number; left: number; width: number }) {
  const board = useContext(BoardContext);
  const target: DropTarget = { op: "insert", line };
  const { setNodeRef, isOver, active } = useDroppable({ id: `edge:${line}`, disabled: board.locked });
  const outcome = isOver && active?.data.current ? describeDrop(board.lines, active.data.current as DragSource, target) : null;
  return (
    <div ref={setNodeRef} style={{ left, width }} className="pointer-events-none absolute inset-y-0 z-20">
      {outcome ? (
        <>
          <span
            aria-hidden
            className={`absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 ${outcome.allowed ? "bg-text" : "bg-muted"}`}
          />
          <ClipDropLabel outcome={outcome} />
        </>
      ) : null}
    </div>
  );
});

type ClipHandleProps = {
  source: DragSource;
  label: string;
  /** The id of the text that says how to move a clip with the keyboard. */
  describedBy: string;
  tabbable: boolean;
  selected: boolean;
  className?: string;
  onSelect: () => void;
  onOpen: () => void;
  onNudge: (delta: -1 | 1) => void;
  children: ReactNode;
};

/**
 * A clip you can pick up. A click selects its line, a double click or Enter
 * opens it, Space picks it up from the keyboard, and Alt with Left or Right
 * swaps it with its neighbour.
 */
export function ClipHandle({
  source,
  label,
  describedBy,
  tabbable,
  selected,
  className = "",
  onSelect,
  onOpen,
  onNudge,
  children,
}: ClipHandleProps) {
  const board = useContext(BoardContext);
  const { setNodeRef, attributes, listeners, isDragging } = useDraggable({
    // Not img:, which the storyboard's handle for the same image already uses.
    id: `clip-img:${source.image}`,
    data: source,
    disabled: board.locked,
  });

  function keyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!isDragging) {
      if (event.key === "Enter") {
        event.preventDefault();
        onOpen();
        return;
      }
      if (event.altKey && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
        event.preventDefault();
        onNudge(event.key === "ArrowLeft" ? -1 : 1);
        return;
      }
      // Focus left here by a mouse click: Space plays, as it does across the editor.
      if (event.key === " " && !event.currentTarget.matches(":focus-visible")) return;
    }
    listeners?.onKeyDown?.(event);
  }

  return (
    <button
      ref={setNodeRef}
      type="button"
      {...attributes}
      {...listeners}
      onKeyDown={keyDown}
      tabIndex={tabbable ? 0 : -1}
      aria-disabled={undefined}
      aria-label={label}
      aria-roledescription="clip"
      aria-describedby={describedBy}
      aria-current={selected ? "true" : undefined}
      data-line={source.fromLine ?? undefined}
      onClick={onSelect}
      onDoubleClick={onOpen}
      className={`relative block h-full w-full cursor-grab touch-manipulation overflow-hidden active:cursor-grabbing ${
        isDragging ? "opacity-35" : ""
      } ${className}`}
    >
      {children}
    </button>
  );
}

/** A frame a file from the desktop can be dropped on, to put it on one line. */
export function FileDropFrame({
  line,
  onFiles,
  className = "",
  children,
}: {
  line: number;
  onFiles: (files: File[], target: DropTarget) => void;
  className?: string;
  children: ReactNode;
}) {
  const board = useContext(BoardContext);
  const target: DropTarget = { op: "place", line };
  const file = useFileDrop(board, target, onFiles);
  const outcome = file.over ? describeFile(board, target) : null;
  return (
    <div {...file.handlers} className={`motion-drop relative ${className} ${outcome?.allowed ? "shadow-[inset_0_0_0_2px_var(--color-text)]" : ""}`}>
      {children}
      {outcome ? <DropLabel outcome={outcome} placement="cell" /> : null}
    </div>
  );
}
