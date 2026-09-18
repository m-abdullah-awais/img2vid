"use client";

import { memo, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { clock, timecode } from "@/lib/format";
import type { Line } from "@/lib/types";
import { Thumb } from "../ui/Thumb";

type Props = {
  lines: Line[];
  /** Narration length, for the ruler when there are no lines yet. */
  seconds: number | null;
  onSelect: (line: number) => void;
};

function describe(line: Line): string {
  const what =
    line.state === "missing"
      ? "no image"
      : line.state === "duplicate"
        ? "more than one image claims it"
        : line.image?.name ?? "image";
  return `Line ${line.line}, ${timecode(line.start)}, ${what}`;
}

const STEPS = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800];

function ticks(from: number, to: number, width: number): number[] {
  const span = Math.max(0.001, to - from);
  const room = Math.max(2, Math.floor(width / 90));
  const step = STEPS.find((candidate) => span / candidate <= room) ?? 3600;
  const list: number[] = [];
  for (let at = Math.ceil(from / step) * step; at < to - step * 0.35; at += step) {
    if (at > from + step * 0.35) list.push(at);
  }
  return list;
}

/**
 * The whole narration as one bar, every line a segment as wide as it is long.
 * A line with no image is hatched amber, so a gap anywhere in a 170 line video
 * shows without scrolling. Segments are memoised and hover is handled once on
 * the bar, so moving the pointer re-renders only the tooltip.
 */
export const CoverageTimeline = memo(function CoverageTimeline({ lines, seconds, onSelect }: Props) {
  const bar = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<{ index: number; left: number; width: number } | null>(null);
  const [cursor, setCursor] = useState(0);

  const from = lines.length ? lines[0].start : 0;
  const to = lines.length ? lines[lines.length - 1].start + lines[lines.length - 1].seconds : seconds ?? 0;
  const marks = useMemo(() => ticks(from, to, 1200), [from, to]);
  const missing = lines.filter((line) => line.state === "missing").length;

  if (!lines.length) {
    if (!seconds) return null;
    return (
      <div aria-label="Coverage timeline" className="flex flex-col gap-1.5">
        <div className="hatch-muted flex h-14 items-center border border-hairline px-4 text-sm text-muted">
          The lines appear here once the narration is transcribed.
        </div>
        <div className="timecode flex justify-between text-xs text-muted">
          <span>0:00</span>
          <span>{clock(seconds)}</span>
        </div>
      </div>
    );
  }

  const index = cursor < lines.length ? cursor : 0;

  function showTip(target: EventTarget | null) {
    const element = (target as HTMLElement | null)?.closest<HTMLElement>("[data-index]");
    const box = bar.current;
    if (!element || !box) return;
    const at = Number(element.dataset.index);
    const left = element.offsetLeft + element.offsetWidth / 2;
    const width = box.offsetWidth;
    setTip((current) => (current && current.index === at ? current : { index: at, left, width }));
  }

  function move(event: KeyboardEvent<HTMLDivElement>) {
    const keys: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, PageDown: 10, PageUp: -10 };
    let next: number | null = null;
    if (event.key in keys) next = Math.min(lines.length - 1, Math.max(0, index + keys[event.key]));
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = lines.length - 1;
    if (event.key === "n" || event.key === "N") {
      // Jump to the next line with no image, wrapping round.
      const order = [...lines.slice(index + 1), ...lines.slice(0, index + 1)];
      const found = order.find((line) => line.state === "missing");
      if (found) next = found.line - 1;
    }
    if (next === null) return;
    event.preventDefault();
    setCursor(next);
    const button = bar.current?.querySelector<HTMLButtonElement>(`[data-index="${next}"]`);
    button?.focus();
  }

  const tipLine = tip ? lines[tip.index] : null;
  const tipLeft = tip ? Math.min(Math.max(tip.left, 90), Math.max(90, tip.width - 90)) : 0;

  return (
    <section aria-labelledby="coverage-title" className="flex flex-col gap-1.5">
      <h2 id="coverage-title" className="sr-only">
        Coverage timeline
      </h2>
      <p id="coverage-help" className="sr-only">
        One segment per line, as wide as the line is long. Arrow keys move along it, N jumps to the next
        line with no image, Enter shows that line in the storyboard.
        {missing ? ` ${missing} lines have no image.` : " Every line has an image."}
      </p>
      <div className="relative">
        {tipLine ? (
          <div
            role="presentation"
            className="pointer-events-none absolute bottom-full z-10 mb-2 -translate-x-1/2 rounded-[var(--radius-control)] border border-hairline bg-panel px-2.5 py-1 text-sm whitespace-nowrap shadow-[0_8px_24px_rgb(0_0_0/0.45)]"
            style={{ left: tipLeft }}
          >
            <span className="timecode">
              Line {tipLine.line}, {timecode(tipLine.start)},{" "}
            </span>
            <span className={tipLine.state === "missing" ? "text-missing" : "text-muted"}>
              {tipLine.state === "missing"
                ? "no image"
                : tipLine.state === "duplicate"
                  ? "more than one image"
                  : tipLine.image?.name}
            </span>
          </div>
        ) : null}
        <div
          ref={bar}
          role="toolbar"
          aria-labelledby="coverage-title"
          aria-describedby="coverage-help"
          onPointerOver={(event: PointerEvent<HTMLDivElement>) => showTip(event.target)}
          onPointerLeave={() => setTip(null)}
          onFocus={(event) => showTip(event.target)}
          onBlur={() => setTip(null)}
          onKeyDown={move}
          className="flex h-14 w-full overflow-hidden border border-hairline bg-graphite"
        >
          {lines.map((line, at) => (
            <Segment key={line.line} line={line} index={at} tabbable={at === index} onSelect={onSelect} />
          ))}
        </div>
      </div>
      <div className="timecode relative h-4 text-xs text-muted" aria-hidden>
        <span className="absolute left-0">{clock(from)}</span>
        {marks.map((at) => (
          <span
            key={at}
            className="absolute -translate-x-1/2 before:absolute before:-top-1.5 before:left-1/2 before:h-1 before:w-px before:bg-hairline"
            style={{ left: `${((at - from) / Math.max(0.001, to - from)) * 100}%` }}
          >
            {clock(at)}
          </span>
        ))}
        <span className="absolute right-0">{clock(to)}</span>
      </div>
    </section>
  );
});

type SegmentProps = {
  line: Line;
  index: number;
  tabbable: boolean;
  onSelect: (line: number) => void;
};

const Segment = memo(function Segment({ line, index, tabbable, onSelect }: SegmentProps) {
  const missing = line.state === "missing";
  return (
    <button
      type="button"
      data-index={index}
      tabIndex={tabbable ? 0 : -1}
      aria-label={describe(line)}
      onClick={() => onSelect(line.line)}
      style={{ flexGrow: Math.max(line.seconds, 0.05), flexBasis: 0 }}
      className={`relative h-full min-w-0 overflow-hidden focus-visible:z-10 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-text after:absolute after:inset-y-0 after:right-0 after:w-px after:bg-graphite/80 ${
        missing ? "hatch" : ""
      } hover:brightness-125`}
    >
      {!missing && line.image ? (
        <Thumb src={line.image.thumb} alt="" className="absolute inset-0 h-full w-full" />
      ) : null}
      {line.state === "duplicate" ? <span aria-hidden className="absolute inset-x-0 top-0 h-1 bg-build" /> : null}
    </button>
  );
});
