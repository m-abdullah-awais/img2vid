"use client";

import { memo, useCallback } from "react";
import type { DropTarget } from "@/lib/arrange";
import { bytes, shortSeconds, timecode } from "@/lib/format";
import type { Line } from "@/lib/types";
import { ImageActions, MoveToLine } from "../dialogs/ImageDialog";
import { FileDropFrame } from "../studio/targets";
import { Thumb, thumbAt } from "../ui/Thumb";

type Props = {
  line: Line | null;
  lines: Line[];
  /** When this line's image comes on screen: its start, or zero for the first. */
  from: number;
  duplicateNames: string[] | null;
  locked: boolean;
  lockedReason: string | null;
  onReplace: (file: File, line: number) => void;
  onRemove: (name: string) => void;
  onMove: (image: string, fromLine: number, toLine: number) => void;
  onFiles: (files: File[], target: DropTarget) => void;
  onShowInStoryboard: (line: number) => void;
};

/**
 * The selected line up close: when it is on screen, its image, every word of
 * its narration, and the same Replace, Remove and Move to line the image
 * dialog offers. A line with no image takes a file dropped on it.
 */
export const Inspector = memo(function Inspector({
  line,
  lines,
  from,
  duplicateNames,
  locked,
  lockedReason,
  onReplace,
  onRemove,
  onMove,
  onFiles,
  onShowInStoryboard,
}: Props) {
  const addFile = useCallback((file: File, at: number) => onFiles([file], { op: "place", line: at }), [onFiles]);

  if (!line) {
    return (
      <div className="flex flex-col gap-2 p-4 text-sm text-muted">
        <h3 className="heading text-xl text-text">{lines.length ? "No line selected" : "No lines yet"}</h3>
        <p>
          {lines.length
            ? "Select a clip on the timeline to see its line here."
            : "Each transcript line becomes a clip on the timeline. Select one to see its image and its words here."}
        </p>
      </div>
    );
  }

  const image = line.image;
  const seconds = Math.max(0, line.end - from);

  return (
    <div className="flex flex-col gap-2.5 px-4 pt-3.5 pb-4">
      <div>
        <h3 className="heading timecode text-2xl leading-7">
          Line {line.line} of {lines.length}
        </h3>
        <p className="timecode text-sm text-muted">
          {timecode(from)} to {timecode(line.end)}, {shortSeconds(seconds)}
        </p>
      </div>

      {image ? (
        <div className="border border-hairline bg-graphite">
          <Thumb
            src={thumbAt(image.thumb, 640)}
            alt={`The image on line ${line.line}`}
            eager
            fit="contain"
            className="aspect-video w-full"
          />
        </div>
      ) : (
        <FileDropFrame line={line.line} onFiles={onFiles} className="hatch flex aspect-video w-full flex-col items-center justify-center gap-2">
          {/* The same upload a file dropped here makes, which also knows a folder paired by position. */}
          <ImageActions line={line.line} image={null} locked={locked} onReplace={addFile} onRemove={onRemove} />
          <span className="rounded-[var(--radius-control)] bg-graphite/90 px-2 py-0.5 text-xs text-text">
            or drop one here
          </span>
        </FileDropFrame>
      )}

      <p className="text-base leading-snug break-words">{line.text}</p>

      {image ? (
        <p className="flex flex-wrap items-baseline gap-x-3 text-sm text-muted">
          <span className="min-w-0 break-all text-text">{image.name}</span>
          <span className="timecode">{bytes(image.bytes)}</span>
        </p>
      ) : (
        <p className="flex items-center gap-1.5 text-sm text-missing">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-missing" />
          No image, so this line is black in the video
        </p>
      )}
      {duplicateNames ? (
        <p className="flex items-start gap-1.5 text-sm">
          <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-build" />
          <span>
            {duplicateNames.length} images claim this line: {duplicateNames.join(", ")}. Keep one.
          </span>
        </p>
      ) : null}
      {locked && lockedReason ? <p className="text-xs text-muted">{lockedReason}</p> : null}

      {image ? (
        <>
          <ImageActions line={line.line} image={image} locked={locked} onReplace={onReplace} onRemove={onRemove} short />
          <MoveToLine key={line.line} lines={lines} line={line.line} image={image} locked={locked} onMove={onMove} compact />
        </>
      ) : null}

      <button
        type="button"
        onClick={() => onShowInStoryboard(line.line)}
        className="w-fit rounded-[var(--radius-control)] text-sm text-muted underline decoration-hairline underline-offset-4 hover:text-text hover:decoration-text"
      >
        Show in storyboard
      </button>
    </div>
  );
});
