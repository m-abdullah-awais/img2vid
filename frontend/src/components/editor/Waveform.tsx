"use client";

import { memo, useEffect, useRef, useState, type RefObject } from "react";
import { api, toApiError } from "@/lib/api";
import { loudness } from "@/lib/timeline";
import type { Peaks } from "@/lib/types";
import { useJobFinished } from "../job/JobProvider";

const MUTED = "#9AA3AD";
const PLAYED = "#E6E8EB";
const FLAT = "#343B44";
const PER_SECOND = 50;
const BAR = 2;
const PITCH = 3;

// Peaks are versioned by the narration, so one answer serves every visit.
const cache = new Map<string, Promise<Peaks>>();

function load(url: string, fresh: boolean): Promise<Peaks> {
  const known = cache.get(url);
  if (known && !fresh) return known;
  const pending = api<Peaks>(url);
  cache.set(url, pending);
  pending.catch(() => cache.delete(url));
  return pending;
}

/**
 * Bars for the part of the narration from `left` px to `left + width` px.
 * Each bar is how loud the narration is under it, so a pause reads as a dip
 * at any zoom. Bars sit on a fixed 3 px grid in timeline space, so scrolling
 * moves them rather than making them shimmer.
 */
function paint(
  canvas: HTMLCanvasElement | null,
  peaks: Peaks | null,
  left: number,
  width: number,
  height: number,
  pps: number,
  duration: number,
  colour: string,
) {
  if (!canvas || width <= 0 || pps <= 0) return;
  const ratio = window.devicePixelRatio || 1;
  const pixelsWide = Math.round(width * ratio);
  const pixelsHigh = Math.round(height * ratio);
  if (canvas.width !== pixelsWide) canvas.width = pixelsWide;
  if (canvas.height !== pixelsHigh) canvas.height = pixelsHigh;
  const context = canvas.getContext("2d");
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);
  const middle = height / 2;
  const end = Math.min(width, duration * pps - left);
  if (end <= 0) return;
  if (!peaks) {
    context.fillStyle = FLAT;
    context.fillRect(0, middle - 0.5, end, 1);
    return;
  }
  context.fillStyle = colour;
  const reach = middle - 3;
  for (let x = -(left % PITCH); x < end; x += PITCH) {
    const value = loudness(peaks.peaks, peaks.perSecond, (left + x) / pps, (left + x + PITCH) / pps);
    const half = Math.max(0.5, (value / 255) * reach);
    context.fillRect(x, middle - half, BAR, half * 2);
  }
}

type Props = {
  /** project.audio.peaks, without perSecond. */
  url: string | null;
  pps: number;
  duration: number;
  /** Visible width of the timeline, which is all the canvas ever covers. */
  viewport: number;
  height: number;
  scroller: RefObject<HTMLDivElement | null>;
  subscribe: (listener: (seconds: number) => void) => () => void;
};

type Result = { key: string; peaks: Peaks | null; state: "ready" | "waiting" | "failed" };

/**
 * The narration's loudness under the clips. The canvas is only as wide as the
 * visible part of the timeline and is drawn again on scroll, zoom and resize,
 * so a long narration zoomed right in never runs into a browser's canvas size
 * limit. A second canvas holds the same bars in the text colour and is
 * clipped to the playhead, so playing costs one style change a frame.
 */
export const Waveform = memo(function Waveform({ url, pps, duration, viewport, height, scroller, subscribe }: Props) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const source = url ? `${url}${url.includes("?") ? "&" : "?"}perSecond=${PER_SECOND}` : null;
  const key = source ? `${source}#${attempt}` : "";
  const current = result && result.key === key ? result : null;
  const peaks = current?.peaks ?? null;
  const waiting = current?.state === "waiting";

  const muted = useRef<HTMLCanvasElement>(null);
  const played = useRef<HTMLCanvasElement>(null);
  const playedBox = useRef<HTMLDivElement>(null);
  const timeRef = useRef(0);
  const view = useRef({ pps, viewport });

  // Asked for while a job ran, the waveform is not made yet: ask again once it ends.
  useJobFinished(() => {
    if (source && current?.state !== "ready") setAttempt((value) => value + 1);
  });

  useEffect(() => {
    if (!source) return;
    let live = true;
    load(source, attempt > 0).then(
      (value) => {
        if (live) setResult({ key, peaks: value, state: "ready" });
      },
      (error: unknown) => {
        if (!live) return;
        const code = toApiError(error).code;
        setResult({ key, peaks: null, state: code === "not_ready" ? "waiting" : "failed" });
      },
    );
    return () => {
      live = false;
    };
  }, [source, key, attempt]);

  useEffect(() => {
    view.current = { pps, viewport };
  }, [pps, viewport]);

  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    let frame = 0;
    const clip = () => {
      const edge = timeRef.current * view.current.pps - box.scrollLeft;
      const hidden = Math.max(0, Math.min(viewport, viewport - edge));
      if (playedBox.current) playedBox.current.style.clipPath = `inset(0 ${hidden}px 0 0)`;
    };
    const draw = () => {
      frame = 0;
      const left = box.scrollLeft;
      paint(muted.current, peaks, left, viewport, height, pps, duration, MUTED);
      paint(played.current, peaks, left, viewport, height, pps, duration, PLAYED);
      clip();
    };
    draw();
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(draw);
    };
    box.addEventListener("scroll", onScroll, { passive: true });
    const unsubscribe = subscribe((seconds) => {
      timeRef.current = seconds;
      clip();
    });
    return () => {
      box.removeEventListener("scroll", onScroll);
      window.cancelAnimationFrame(frame);
      unsubscribe();
    };
  }, [peaks, pps, viewport, height, duration, scroller, subscribe]);

  return (
    <div role="img" aria-label={waiting ? "Waveform of the narration, drawn once the running job finishes" : "Waveform of the narration"} className="relative" style={{ height }}>
      <div className="sticky left-0 h-full" style={{ width: viewport }}>
        <canvas ref={muted} aria-hidden className="absolute inset-0 h-full w-full" />
        <div ref={playedBox} aria-hidden className="absolute inset-0" style={{ clipPath: "inset(0 100% 0 0)" }}>
          <canvas ref={played} className="h-full w-full" />
        </div>
        {waiting ? (
          <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 bg-graphite px-1 text-xs text-muted">
            The waveform is drawn once the running job finishes
          </span>
        ) : null}
      </div>
    </div>
  );
});
