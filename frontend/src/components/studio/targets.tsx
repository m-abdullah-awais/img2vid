"use client";

import { useDraggable, useDroppable } from "@dnd-kit/core";
import {
  createContext,
  useContext,
  useRef,
  useState,
  type DragEvent,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { describeDrop, type DragSource, type DropTarget, type Outcome } from "@/lib/arrange";
import type { Line } from "@/lib/types";

// The storyboard's drop targets. Each is a thin shell around content its
// parent built, so when dnd-kit re-renders the shells as the pointer moves
// from one target to the next, the rows inside them are not rendered again.

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
