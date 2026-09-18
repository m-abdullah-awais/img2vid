"use client";

import { ImagePlus } from "lucide-react";
import { memo } from "react";
import { pad, shortSeconds, timecode } from "@/lib/format";
import type { Line } from "@/lib/types";
import { ProgressBar } from "../ui/ProgressBar";
import { Thumb } from "../ui/Thumb";
import { nudgeKey, type RowHandlers } from "./LineRow";
import { DragHandle, LineTarget } from "./targets";

type CellProps = RowHandlers & {
  line: Line;
  total: number;
  locked: boolean;
  progress: number | null;
};

type GridProps = RowHandlers & {
  lines: Line[];
  total: number;
  locked: boolean;
  uploads: Record<number, number>;
};

/** The storyboard as a contact sheet, for judging the pictures rather than the words. */
export function GridView({ lines, total, locked, uploads, ...handlers }: GridProps) {
  return (
    <div role="list" aria-label="Storyboard" className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
      {lines.map((line) => (
        <GridCell
          key={line.line}
          line={line}
          total={total}
          locked={locked}
          progress={uploads[line.line] ?? null}
          {...handlers}
        />
      ))}
    </div>
  );
}

/** One line as a contact sheet frame. Dropping on it places; inserting is a list view gesture. */
export const GridCell = memo(function GridCell({
  line,
  total,
  locked,
  progress,
  onOpen,
  onPick,
  onFiles,
  onNudge,
}: CellProps) {
  const image = line.image;
  const missing = line.state === "missing";
  return (
    <LineTarget
      dropId={`cell:${line.line}`}
      target={{ op: "place", line: line.line }}
      placement="cell"
      onFiles={onFiles}
      id={`line-${line.line}`}
      tabIndex={-1}
      role="listitem"
      aria-label={`Line ${line.line}`}
      onKeyDown={(event) => nudgeKey(event, line.line, onNudge)}
      className="lazy-cell flex flex-col gap-1.5 rounded-[var(--radius-control)] p-1.5 focus:outline-2 focus:outline-text"
    >
      <div className="relative">
        {image ? (
          <DragHandle
            source={{ image: image.name, thumb: image.thumb, fromLine: line.line }}
            label={`${image.name} on line ${line.line}. Press Space to move it.`}
            onOpen={() => onOpen(line.line)}
            className={`aspect-video w-full border ${line.state === "duplicate" ? "border-build" : "border-hairline"}`}
          >
            <Thumb src={image.thumb} alt="" className="h-full w-full" />
          </DragHandle>
        ) : (
          <button
            type="button"
            disabled={locked}
            onClick={() => onPick(line.line)}
            aria-label={`Add an image to line ${line.line}`}
            className="hatch flex aspect-video w-full items-center justify-center rounded-[var(--radius-frame)] hover:brightness-125 disabled:cursor-not-allowed"
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
      <div className="timecode flex items-baseline justify-between gap-2 text-sm">
        <span className={missing ? "text-missing" : "text-text"}>{pad(line.line, Math.max(3, String(total).length))}</span>
        <span className="text-muted">
          {timecode(line.start)}
          <span className="ml-2">{shortSeconds(line.seconds)}</span>
        </span>
      </div>
      <p className="line-clamp-2 text-xs text-muted">{line.text}</p>
    </LineTarget>
  );
});
