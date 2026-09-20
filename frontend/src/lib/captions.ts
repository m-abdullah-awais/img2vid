// Where the captions sit and how big they are, as fractions of the frame.
//
// backend/i2v/captions.py is the other half of this file: caption_style()
// turns the same numbers into an ASS style, libass burns it onto each image,
// and the preview lays the same thing out in CSS. Pure functions only, so
// what is watched and what is built cannot drift apart.

import { frameSize } from "@/lib/timeline";
import type { CaptionLook, CaptionPlace, CaptionSettings, CaptionSize } from "@/lib/types";

/** Font size as a fraction of the frame height. SIZES in captions.py. */
export const SIZES: Record<CaptionSize, number> = { small: 0.04, medium: 0.05, large: 0.062 };

/** Kept clear of each side, as a fraction of the frame width. */
export const SIDE = 0.06;

/** Outline thickness as a fraction of the frame height, never under a pixel. */
export const OUTLINE = 0.0022;

/** The furthest in from an edge the engine will put them, as a percentage. */
export const MAX_DISTANCE = 45;

/** What the API stores for a project that has never been asked about captions. */
export const CAPTION_DEFAULTS: CaptionSettings = {
  on: false,
  place: "bottom",
  distance: 8,
  size: "medium",
  look: "outline",
};

/*
  Arial, in units of its 2048 unit em square: the ascender is 1854 and the
  descender 434. libass asks for a face whose ascender plus descender comes to
  the style's font size, so a caption set at 54 stands 54 px from ascender to
  descender while its em square is only 48.3 px. Getting this wrong puts the
  preview's text about 10 percent too large, so it was measured on burned in
  frames rather than assumed, at all three sizes and in all three places.

  Checked again after the fact by building a frame and screenshotting the
  preview at the same settings: the words sat within 0.1 percent of the frame
  height of each other at the bottom, and 0.3 percent at the top.
*/
const ASCENDER = 1854;
const DESCENDER = 434;
const EM_UNITS = 2048;

/** One line of captions is exactly its ascender plus its descender tall. */
export const LINE_HEIGHT = (ASCENDER + DESCENDER) / EM_UNITS;
const EM_PER_POINT = EM_UNITS / (ASCENDER + DESCENDER);

/** The typefaces to try, in the order libass would. The engine sets Arial. */
export const CAPTION_FONT = "Arial, Helvetica, sans-serif";

export type CaptionGeometry = {
  /** CSS font size, as a fraction of the frame height. */
  font: number;
  /** One line's height, as a multiple of the font size. */
  lineHeight: number;
  /** How far the outline reaches out of a letter, as a fraction of the height. */
  outline: number;
  /** In from the edge the text sits against, as a fraction of the height. */
  margin: number;
  /** Clear of each side, as a fraction of the width. */
  side: number;
};

/**
 * The caption geometry for a build at `size`, every length a fraction of the
 * frame so it holds at any preview size and for a vertical project.
 *
 * Each figure is rounded to the whole pixel the engine will use first, then
 * divided by the frame, so a small output and its preview agree: the outline's
 * one pixel floor, for instance, is a real difference at 320 x 180.
 */
export function captionGeometry(size: string, settings: CaptionSettings): CaptionGeometry {
  const { width, height } = frameSize(size);
  const points = Math.max(10, Math.round(height * (SIZES[settings.size] ?? SIZES.medium)));
  const outline = Math.max(1, Math.round(height * OUTLINE * 10) / 10);
  const distance = Math.min(MAX_DISTANCE, Math.max(0, settings.distance)) / 100;
  return {
    font: (points * EM_PER_POINT) / height,
    lineHeight: LINE_HEIGHT,
    outline: outline / height,
    margin: Math.round(height * distance) / height,
    side: Math.round(width * SIDE) / width,
  };
}

/**
 * One line's words as libass is given them: whitespace collapsed, and braces
 * turned into parentheses so they cannot open a style tag. ass_text() does the
 * same, so a line reads here exactly as it will in the video.
 */
export function captionText(text: string | null | undefined): string {
  return (text ?? "").split(/\s+/).filter(Boolean).join(" ").replace(/\{/g, "(").replace(/\}/g, ")");
}

const PLACE_WORD: Record<CaptionPlace, string> = {
  top: "top",
  middle: "middle",
  bottom: "bottom",
};

const LOOK_WORD: Record<CaptionLook, string> = {
  outline: "with an outline",
  band: "on a band",
};

/** What the build will produce, in one line. Null when captions are off. */
export function captionSummary(settings: CaptionSettings | null | undefined): string | null {
  if (!settings?.on) return null;
  const place = PLACE_WORD[settings.place] ?? PLACE_WORD.bottom;
  const look = LOOK_WORD[settings.look] ?? LOOK_WORD.outline;
  return `Captions on: each line's words across the ${place}, ${settings.size} ${look}.`;
}

/** The distance readout: 8% and 8.5%, never 8.0%. */
export function distanceText(distance: number): string {
  return `${Number.isInteger(distance) ? distance : distance.toFixed(1)}%`;
}

export function sameCaptions(a: CaptionSettings, b: CaptionSettings): boolean {
  return (
    a.on === b.on &&
    a.place === b.place &&
    a.distance === b.distance &&
    a.size === b.size &&
    a.look === b.look
  );
}
