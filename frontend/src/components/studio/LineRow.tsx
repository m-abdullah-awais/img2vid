"use client";

import { Ellipsis, ImagePlus } from "lucide-react";
import { memo, type KeyboardEvent } from "react";
import type { DropTarget } from "@/lib/arrange";
import { pad, shortSeconds, timecode } from "@/lib/format";
import type { Line } from "@/lib/types";
import { IconButton } from "../ui/Button";
import { ProgressBar } from "../ui/ProgressBar";
import { Thumb } from "../ui/Thumb";
import { DragHandle, GapTarget, LineTarget } from "./targets";

export type RowHandlers = {
  onOpen: (line: number) => void;
  onPick: (line: number) => void;
  onFiles: (files: File[], target: DropTarget) => void;
  onNudge: (line: number, delta: -1 | 1) => void;
};

type Props = RowHandlers & {
  line: Line;
  total: number;
  locked: boolean;
  duplicateNames: string[] | null;
  /** 0..1 while a file is uploading onto this line. */
  progress: number | null;
};

/** Alt with an arrow swaps the image with its neighbour. */
export function nudgeKey(event: KeyboardEvent, line: number, onNudge: RowHandlers["onNudge"]) {
  if (!event.altKey || event.ctrlKey || event.metaKey) return;
  if (event.key === "ArrowUp" || event.key === "ArrowDown") {
    event.preventDefault();
    onNudge(line, event.key === "ArrowUp" ? -1 : 1);
  }
}

export function StateNote({ line, duplicateNames }: { line: Line; duplicateNames: string[] | null }) {
  if (line.state === "missing") {
    return (
      <span className="flex items-center gap-1.5 text-missing">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-missing" />
        No image
      </span>
    );
  }
  if (line.state === "duplicate") {
    const names = duplicateNames && duplicateNames.length ? duplicateNames.join(", ") : line.image?.name;
    return (
      <span className="flex items-start gap-1.5 text-text">
        <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-build" />
        <span>
          {duplicateNames ? `${duplicateNames.length} images claim this line: ` : "More than one image claims this line: "}
          {names}
        </span>
      </span>
    );
  }
  return <span className="block truncate text-muted">{line.image?.name}</span>;
}

/** One transcript line in the list view. Memoised: a drag re-renders its shells, not this. */
export const LineRow = memo(function LineRow({
  line,
  total,
  locked,
  duplicateNames,
  progress,
  onOpen,
  onPick,
  onFiles,
  onNudge,
}: Props) {
  const number = pad(line.line, Math.max(3, String(total).length));
  const missing = line.state === "missing";
  const image = line.image;

  return (
    <div role="listitem" aria-label={`Line ${line.line}`}>
      <GapTarget line={line.line} onFiles={onFiles} />
      <LineTarget
        dropId={`line:${line.line}`}
        target={{ op: "place", line: line.line }}
        placement="row"
        onFiles={onFiles}
        id={`line-${line.line}`}
        tabIndex={-1}
        onKeyDown={(event) => nudgeKey(event, line.line, onNudge)}
        className="lazy-row grid grid-cols-[6.5rem_minmax(0,1fr)] items-start gap-x-3 gap-y-1 rounded-[var(--radius-control)] border-b border-hairline px-2 py-2 focus:outline-2 focus:outline-offset-[-2px] focus:outline-text sm:grid-cols-[3rem_4.25rem_8rem_minmax(0,1fr)_auto] sm:items-center sm:gap-x-4 sm:px-3"
      >
        <div className="timecode flex items-baseline gap-3 max-sm:col-start-2 max-sm:row-start-1 sm:contents">
          <span className={`text-base ${missing ? "text-missing" : "text-text"}`}>{number}</span>
          <span className="text-sm text-muted">{timecode(line.start)}</span>
        </div>

        <div className="relative max-sm:col-start-1 max-sm:row-span-3 max-sm:row-start-1">
          {image ? (
            <DragHandle
              source={{ image: image.name, thumb: image.thumb, fromLine: line.line }}
              label={`${image.name} on line ${line.line}. Press Space to move it.`}
              onOpen={() => onOpen(line.line)}
              className="aspect-video w-full border border-hairline sm:w-32"
            >
              <Thumb src={image.thumb} alt="" className="h-full w-full" />
            </DragHandle>
          ) : (
            <button
              type="button"
              disabled={locked}
              onClick={() => onPick(line.line)}
              aria-label={`Add an image to line ${line.line}`}
              className="hatch flex aspect-video w-full items-center justify-center rounded-[var(--radius-frame)] text-text hover:brightness-125 disabled:cursor-not-allowed sm:w-32"
            >
              <span className="flex items-center gap-1.5 rounded-[var(--radius-control)] bg-graphite/85 px-2 py-0.5 text-xs font-medium">
                <ImagePlus size={14} aria-hidden />
                Add image
              </span>
            </button>
          )}
          {progress !== null ? (
            <div className="absolute inset-x-1 bottom-1">
              <ProgressBar value={progress} label={`Uploading to line ${line.line}`} thin />
            </div>
          ) : null}
        </div>

        <div className="min-w-0 max-sm:col-start-2">
          <p className="line-clamp-2 text-base leading-snug break-words">{line.text}</p>
          <div className="text-sm">
            <StateNote line={line} duplicateNames={duplicateNames} />
          </div>
        </div>

        <div className="flex items-center gap-2 max-sm:col-start-2 sm:justify-end">
          <span className="timecode w-10 text-right text-sm text-muted" title="How long this line is on screen">
            {shortSeconds(line.seconds)}
          </span>
          {image ? (
            // Move to line, replace and remove live in this dialog rather than on
            // every row: 170 rows of number fields read as a form, not a storyboard.
            <IconButton label={`Image options for line ${line.line}`} onClick={() => onOpen(line.line)}>
              <Ellipsis size={18} aria-hidden />
            </IconButton>
          ) : (
            <span className="w-9 max-sm:hidden" aria-hidden />
          )}
        </div>
      </LineTarget>
    </div>
  );
});
