"use client";

import { memo, useEffect, useId, useMemo, useRef, type KeyboardEvent } from "react";
import type { DropTarget } from "@/lib/arrange";
import { shortSeconds, timecode } from "@/lib/format";
import { onScreenFrom } from "@/lib/timeline";
import type { Line } from "@/lib/types";
import { ClipHandle, ClipTarget, EdgeTarget } from "../studio/targets";
import { ProgressBar } from "../ui/ProgressBar";
import { Thumb } from "../ui/Thumb";

type Handlers = {
  onSelect: (line: number) => void;
  onOpen: (line: number) => void;
  onFiles: (files: File[], target: DropTarget) => void;
  onNudge: (line: number, delta: -1 | 1) => void;
};

type Props = Handlers & {
  lines: Line[];
  /** Pixels per second. */
  pps: number;
  selected: number | null;
  /** 0..1 while a file is uploading onto a line. */
  uploads: Record<number, number>;
};

/** Where a clip is on screen, in seconds: the first one from zero, every one to its line's end. */
type Span = { from: number; to: number };

export function describeClip(line: Line, span: Span): string {
  const what =
    line.state === "missing"
      ? "no image"
      : line.state === "duplicate"
        ? "more than one image claims it"
        : line.image?.name ?? "image";
  return `Line ${line.line}, ${timecode(span.from)} to ${timecode(span.to)}, ${what}`;
}

/** The width of the insert zone at a cut: a few pixels, never most of a narrow clip. */
function edgeWidth(before: number, after: number): number {
  return Math.max(4, Math.min(14, Math.min(before, after) * 0.3));
}

/**
 * The image track: one clip per line, as long as the line is on screen. Clips
 * are memoised on their line and their pixel box, so the playhead moving never
 * renders them, and a new selection renders only the two it changed.
 */
export const ClipTrack = memo(function ClipTrack({ lines, pps, selected, uploads, onSelect, onOpen, onFiles, onNudge }: Props) {
  const helpId = useId();
  const track = useRef<HTMLDivElement>(null);

  const spans = useMemo<Span[]>(
    () => lines.map((line, index) => ({ from: onScreenFrom(lines, index), to: Math.max(line.end, onScreenFrom(lines, index)) })),
    [lines],
  );

  // Arrow keys move the selection; when focus was already on a clip, it follows.
  useEffect(() => {
    const box = track.current;
    if (!box || selected === null) return;
    const focused = document.activeElement;
    if (!(focused instanceof HTMLElement) || !box.contains(focused)) return;
    const clip = box.querySelector<HTMLElement>(`[data-clip="${selected}"] > button`);
    if (clip && clip !== focused) clip.focus({ preventScroll: true });
  }, [selected]);

  const tabbable = selected ?? (lines.length ? lines[0].line : null);

  return (
    <div ref={track} role="group" aria-label="Images, one clip per line" aria-describedby={helpId} className="relative h-16">
      <p id={helpId} className="sr-only">
        Each clip is one line, as long as its image is on screen. Click a clip to select its line, and double click
        it or press Enter to open it. Space picks its image up; the arrow keys then step through the clips and the
        cuts between them, and Space drops it. Dropping on a clip swaps, dropping on a cut inserts. Alt with Left or
        Right swaps it with the clip beside it.
      </p>
      {lines.map((line, index) => (
        <Clip
          key={line.line}
          line={line}
          from={spans[index].from}
          to={spans[index].to}
          pps={pps}
          selected={line.line === selected}
          tabbable={line.line === tabbable}
          progress={uploads[line.line] ?? null}
          helpId={helpId}
          onSelect={onSelect}
          onOpen={onOpen}
          onFiles={onFiles}
          onNudge={onNudge}
        />
      ))}
      {lines.map((line, index) => {
        const at = spans[index].from * pps;
        const before = index > 0 ? (spans[index - 1].to - spans[index - 1].from) * pps : Infinity;
        const after = (spans[index].to - spans[index].from) * pps;
        const width = edgeWidth(before, after);
        return <EdgeTarget key={line.line} line={line.line} left={Math.max(0, at - width / 2)} width={width} />;
      })}
    </div>
  );
});

type ClipProps = Handlers & {
  line: Line;
  from: number;
  to: number;
  pps: number;
  selected: boolean;
  tabbable: boolean;
  progress: number | null;
  helpId: string;
};

const badge = "timecode pointer-events-none absolute left-1 rounded-[var(--radius-frame)] bg-graphite/85 px-1 text-xs leading-4 text-text";

const Clip = memo(function Clip({
  line,
  from,
  to,
  pps,
  selected,
  tabbable,
  progress,
  helpId,
  onSelect,
  onOpen,
  onFiles,
  onNudge,
}: ClipProps) {
  const left = from * pps;
  const box = Math.max(1, (to - from) * pps);
  // A one pixel cut between clips, as long as there is room for it.
  const width = box > 3 ? box - 1 : box;
  const image = line.image;
  const missing = line.state === "missing" || !image;
  const label = describeClip(line, { from, to });

  const content = (
    <>
      {!missing && image ? <Thumb src={image.thumb} alt="" className="absolute inset-0 h-full w-full" /> : null}
      {line.state === "duplicate" ? <span aria-hidden className="absolute inset-x-0 top-0 h-[3px] bg-build" /> : null}
      {width >= 40 ? (
        <span aria-hidden className={`${badge} top-1`}>
          {shortSeconds(to - from)}
        </span>
      ) : null}
      {width >= 58 ? (
        <span aria-hidden className={`${badge} bottom-1`}>
          {timecode(from)}
        </span>
      ) : null}
      {progress !== null ? (
        <span className="absolute inset-x-1 bottom-1 block">
          <ProgressBar value={progress} label={`Uploading to line ${line.line}`} thin />
        </span>
      ) : null}
    </>
  );

  // Keyboard focus sits outside the selection ring, so the two never merge.
  const frame =
    "focus-visible:z-20 focus-visible:outline-2 focus-visible:outline-offset-[5px] focus-visible:outline-text";

  return (
    <ClipTarget line={line.line} left={left} width={width} selected={selected} onFiles={onFiles}>
      {!missing && image ? (
        <ClipHandle
          source={{ image: image.name, thumb: image.thumb, fromLine: line.line }}
          label={label}
          describedBy={helpId}
          tabbable={tabbable}
          selected={selected}
          onSelect={() => onSelect(line.line)}
          onOpen={() => onOpen(line.line)}
          onNudge={(delta) => onNudge(line.line, delta)}
          className={`bg-graphite ${frame}`}
        >
          {content}
        </ClipHandle>
      ) : (
        <button
          type="button"
          tabIndex={tabbable ? 0 : -1}
          aria-label={label}
          aria-describedby={helpId}
          aria-current={selected ? "true" : undefined}
          data-line={line.line}
          onClick={() => onSelect(line.line)}
          onDoubleClick={() => onOpen(line.line)}
          onKeyDown={(event: KeyboardEvent<HTMLButtonElement>) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onOpen(line.line);
            }
          }}
          className={`hatch relative block h-full w-full overflow-hidden ${frame}`}
        >
          {content}
        </button>
      )}
    </ClipTarget>
  );
});
