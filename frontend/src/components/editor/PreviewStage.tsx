"use client";

import { memo, useEffect, useRef, type CSSProperties } from "react";
import { apiUrl } from "@/lib/api";
import { frameSize, stageColour, stageSrc } from "@/lib/timeline";
import type { Line, RenderSettings } from "@/lib/types";

type Props = {
  /** The line on screen, or null when there are no lines yet. */
  line: Line | null;
  settings: RenderSettings;
  /** Said on the stage when there is nothing to show, such as before a transcript. */
  note: string | null;
  onToggle: () => void;
};

/**
 * The video frame as the build will make it: its aspect ratio, its fit and its
 * background, letterboxed inside a darker viewing well.
 *
 * Two <img> layers take turns. The next image loads and decodes in the hidden
 * one, and only then do they swap, so a cut is always from one picture
 * straight to the next and never through an empty frame. A line with no image
 * is a full black frame whatever the background is, because that is what the
 * engine renders for it.
 */
export const PreviewStage = memo(function PreviewStage({ line, settings, note, onToggle }: Props) {
  const { width, height } = frameSize(settings.size);
  const colour = stageColour(settings.background);
  const fit = settings.fit === "cover" ? "object-cover" : "object-contain";
  const src = line ? (line.image ? apiUrl(stageSrc(line.image)) : "") : null;

  const stage = useRef<HTMLDivElement>(null);
  const first = useRef<HTMLImageElement>(null);
  const second = useRef<HTMLImageElement>(null);
  const black = useRef<HTMLDivElement>(null);
  const front = useRef(0);
  const shown = useRef<string | null>(null);

  useEffect(() => {
    const frame = stage.current;
    const cover = black.current;
    if (!first.current || !second.current || !frame || !cover) return;
    const layers = [first.current, second.current];

    // No lines yet: the background alone.
    if (src === null) {
      cover.hidden = true;
      for (const layer of layers) layer.style.visibility = "hidden";
      shown.current = null;
      frame.dataset.shown = "none";
      return;
    }
    // A line without an image: black over whatever was showing, which stays
    // loaded underneath in case the next line brings it back.
    if (src === "") {
      cover.hidden = false;
      frame.dataset.shown = "black";
      return;
    }
    if (shown.current === src) {
      cover.hidden = true;
      frame.dataset.shown = src;
      return;
    }

    let live = true;
    const current = layers[front.current] as HTMLImageElement;
    const next = layers[1 - front.current] as HTMLImageElement;
    const reveal = () => {
      if (!live) return;
      next.style.visibility = "visible";
      current.style.visibility = "hidden";
      cover.hidden = true;
      front.current = 1 - front.current;
      shown.current = src;
      frame.dataset.shown = src;
    };
    if (next.getAttribute("src") !== src) next.src = src;
    next.decode().then(reveal, reveal);
    return () => {
      live = false;
    };
  }, [src]);

  const well = { containerType: "size", "--ratio": `${width} / ${height}` } as CSSProperties;
  const frameStyle: CSSProperties = {
    aspectRatio: `${width} / ${height}`,
    width: `min(100cqw, calc(100cqh * ${width / height}))`,
    backgroundColor: colour,
  };
  const label = !line
    ? "Preview"
    : line.image
      ? `Preview of line ${line.line}: ${line.image.name}`
      : `Preview of line ${line.line}: no image, a black frame`;

  return (
    <div
      data-well
      style={well}
      className="flex aspect-[var(--ratio)] max-h-[62svh] w-full items-center justify-center bg-graphite p-2 sm:p-3 lg:aspect-auto lg:h-[var(--stage-h)] lg:max-h-none"
    >
      <div
        ref={stage}
        role="img"
        aria-label={label}
        data-line={line?.line ?? ""}
        onClick={onToggle}
        style={frameStyle}
        className="relative max-h-full cursor-pointer overflow-hidden"
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- runtime URLs from the local engine */}
        <img ref={first} alt="" draggable={false} className={`absolute inset-0 h-full w-full ${fit}`} />
        {/* eslint-disable-next-line @next/next/no-img-element -- runtime URLs from the local engine */}
        <img ref={second} alt="" draggable={false} className={`absolute inset-0 h-full w-full ${fit}`} />
        <div ref={black} hidden className="absolute inset-0 bg-[#000]" />
        {note ? (
          <p className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-muted">
            <span className="max-w-[40ch] rounded-[var(--radius-control)] bg-graphite/90 px-3 py-2">{note}</span>
          </p>
        ) : null}
      </div>
    </div>
  );
});
