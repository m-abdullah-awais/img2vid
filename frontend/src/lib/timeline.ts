// The editor's arithmetic: which line is on screen at a moment, where a clip
// sits on the timeline, what the ruler marks, and how the stage is framed.
// Pure functions only, so the preview, the timeline and the checks agree.

import type { ImageRef, Line } from "@/lib/types";

/**
 * When a line's image comes on screen in the built video. Its own start,
 * except the first, which the engine pulls back to zero so the video never
 * opens on black.
 */
export function onScreenFrom(lines: Line[], index: number): number {
  if (index <= 0) return 0;
  return lines[index]?.start ?? 0;
}

/**
 * The index of the line on screen at `time`: the last one that has started.
 * Before the first line starts, that is still the first line. -1 with no lines.
 */
export function lineIndexAt(lines: Line[], time: number): number {
  if (!lines.length) return -1;
  let low = 0;
  let high = lines.length - 1;
  let found = 0;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (lines[middle].start <= time) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found;
}

/** The same image URL the API handed back, at another width, keeping its version. */
export function withWidth(url: string, width: number): string {
  const [path, query = ""] = url.split("?");
  const params = new URLSearchParams(query);
  params.set("w", String(Math.round(width)));
  return `${path}?${params.toString()}`;
}

/**
 * What the stage shows for an image. The original file, since the stage is
 * as large as the video frame; a browser cannot show TIFF, so those come
 * through the thumbnail route at 1280 wide instead.
 */
export function stageSrc(image: ImageRef): string {
  return /\.tiff?$/i.test(image.name) ? withWidth(image.thumb, 1280) : image.url;
}

/** "1920x1080" as numbers. Anything unreadable is taken as 16:9. */
export function frameSize(size: string | null | undefined): { width: number; height: number } {
  const match = /^\s*(\d+)\s*[x:*]\s*(\d+)\s*$/i.exec(size ?? "");
  const width = match ? Number(match[1]) : 0;
  const height = match ? Number(match[2]) : 0;
  if (width > 0 && height > 0) return { width, height };
  return { width: 16, height: 9 };
}

/**
 * The render setting's background as a CSS colour. The engine takes a colour
 * name or a hex value, and ffmpeg also accepts 0xRRGGBB, which CSS does not.
 */
export function stageColour(background: string | null | undefined): string {
  const value = (background ?? "").trim();
  if (/^#[0-9a-f]{3,8}$/i.test(value)) return value;
  if (/^0x[0-9a-f]{6}([0-9a-f]{2})?$/i.test(value)) return `#${value.slice(2)}`;
  if (/^[a-z]{3,30}$/i.test(value)) return value.toLowerCase();
  return "black";
}

// Zoom is pixels per second of narration.

/** The most a second can be drawn at: a 1 s tick 240 px apart. */
export const MAX_PPS = 240;
export const ZOOM_STEP = 1.5;

/** Keep a zoom between showing the whole narration and MAX_PPS. */
export function clampZoom(pps: number, fit: number): number {
  const low = Math.max(fit, 0.01);
  return Math.min(Math.max(pps, low), Math.max(low, MAX_PPS));
}

const STEPS = [1, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];

/** The ruler's step: the finest one that keeps its labels `gap` px apart. */
export function tickStep(pps: number, gap = 70): number {
  return STEPS.find((step) => step * pps >= gap) ?? 3600;
}

/** Unlabelled ticks between two labelled ones. */
export function minorStep(step: number): number {
  if (step === 15) return 5;
  if (step === 1) return 0.5;
  return step / 5;
}

/**
 * How loud the narration is between two moments, 0..255: the root mean
 * square of the peaks in the span, or the one peak it falls in when the span
 * is narrower than a peak. The mean rather than the loudest peak, because at
 * a wide zoom every half second holds a loud syllable somewhere, and the
 * loudest would draw a solid block with no pauses in it.
 */
export function loudness(peaks: number[], perSecond: number, from: number, to: number): number {
  const first = Math.max(0, Math.floor(from * perSecond));
  const last = Math.min(peaks.length, Math.max(first + 1, Math.ceil(to * perSecond)));
  if (last <= first) return 0;
  let sum = 0;
  for (let index = first; index < last; index += 1) sum += peaks[index] * peaks[index];
  return Math.sqrt(sum / (last - first));
}
