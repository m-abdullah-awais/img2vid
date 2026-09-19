"use client";

import { Minus, Plus } from "lucide-react";
import {
  memo,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type Ref,
  type RefObject,
} from "react";
import type { DropTarget } from "@/lib/arrange";
import { clock, timecode } from "@/lib/format";
import { clampZoom, minorStep, tickStep, ZOOM_STEP } from "@/lib/timeline";
import type { Line } from "@/lib/types";
import { ClipTrack } from "./ClipTrack";
import type { Playback } from "./usePlayback";
import { Waveform } from "./Waveform";

export type TimelineHandle = {
  zoomIn: () => void;
  zoomOut: () => void;
  fit: () => void;
};

const RULER = 32;
const IMAGES = 64;
const VOICE = 44;

type Props = {
  lines: Line[];
  duration: number;
  selected: number | null;
  playing: boolean;
  playback: Pick<Playback, "subscribe" | "seek" | "time" | "toggle">;
  /** project.audio.peaks */
  peaks: string | null;
  uploads: Record<number, number>;
  onSelect: (line: number) => void;
  onOpen: (line: number) => void;
  onFiles: (files: File[], target: DropTarget) => void;
  onNudge: (line: number, delta: -1 | 1) => void;
  ref?: Ref<TimelineHandle>;
};

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * A ruler, the image track and the voice track, scrolling sideways together
 * under labels that stay put. Zoom is pixels per second; Fit shows the whole
 * narration. The playhead is moved by a CSS transform from the playback clock
 * and is the only thing on the page that moves while the preview plays.
 */
export function Timeline({
  lines,
  duration,
  selected,
  playing,
  playback,
  peaks,
  uploads,
  onSelect,
  onOpen,
  onFiles,
  onNudge,
  ref,
}: Props) {
  const { subscribe, seek, time, toggle } = playback;
  const scroller = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const playhead = useRef<HTMLDivElement>(null);
  const handle = useRef<HTMLDivElement>(null);

  const [viewport, setViewport] = useState(0);
  /** Pixels per second, or null for Fit. */
  const [zoom, setZoom] = useState<number | null>(null);

  const span = Math.max(duration, 0.001);
  const fit = viewport > 0 ? viewport / span : 1;
  const pps = zoom === null ? fit : clampZoom(zoom, fit);
  const width = Math.max(viewport, Math.ceil(span * pps));
  const fitting = zoom === null || pps <= fit * 1.0001;

  const view = useRef({ pps, fit, duration });
  const playingRef = useRef(playing);
  const anchor = useRef<{ time: number; x: number } | null>(null);
  const scrub = useRef<{ pointer: number; touch: boolean; x: number; y: number } | null>(null);
  const userScrolled = useRef(0);
  const autoUntil = useRef(0);
  const spoken = useRef("");

  useEffect(() => {
    playingRef.current = playing;
  }, [playing]);

  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const observer = new ResizeObserver(() => setViewport(box.clientWidth));
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  /** The playhead's place, and the slider's value when it is still. */
  const place = useCallback((seconds: number) => {
    const line = playhead.current;
    if (line) line.style.transform = `translateX(${seconds * view.current.pps}px)`;
    const knob = handle.current;
    if (!knob) return;
    const text = `${timecode(seconds)} of ${timecode(view.current.duration)}`;
    if (!playingRef.current && text !== spoken.current) {
      spoken.current = text;
      knob.setAttribute("aria-valuenow", seconds.toFixed(1));
      knob.setAttribute("aria-valuetext", text);
    }
  }, []);

  // A zoom keeps the moment under the pointer, or under the playhead, where it was.
  useLayoutEffect(() => {
    view.current = { pps, fit, duration };
    const box = scroller.current;
    const wanted = anchor.current;
    anchor.current = null;
    if (box && wanted) box.scrollLeft = Math.max(0, wanted.time * pps - wanted.x);
    // React may just have written the slider's text for a new length; write the real one back.
    spoken.current = "";
    place(time());
  }, [pps, fit, duration, place, time]);

  const zoomBy = useCallback((factor: number, at?: number) => {
    const box = scroller.current;
    if (!box) return;
    const { pps: now, fit: whole } = view.current;
    const next = clampZoom(now * factor, whole);
    if (Math.abs(next - now) < 1e-6) return;
    let x = at;
    if (x === undefined) {
      const head = time() * now - box.scrollLeft;
      x = head >= 0 && head <= box.clientWidth ? head : box.clientWidth / 2;
    }
    anchor.current = { time: (box.scrollLeft + x) / now, x };
    setZoom(next <= whole * 1.0001 ? null : next);
  }, [time]);

  useImperativeHandle(
    ref,
    () => ({
      zoomIn: () => zoomBy(ZOOM_STEP),
      zoomOut: () => zoomBy(1 / ZOOM_STEP),
      fit: () => setZoom(null),
    }),
    [zoomBy],
  );

  // Ctrl with the wheel zooms around the pointer. React's wheel listener is
  // passive, so this one is added by hand to be allowed to stop page zoom.
  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) {
        userScrolled.current = performance.now();
        return;
      }
      event.preventDefault();
      const x = event.clientX - box.getBoundingClientRect().left;
      zoomBy(Math.exp(-event.deltaY * 0.002), x);
    };
    const onTouch = () => {
      userScrolled.current = performance.now();
    };
    const onPointer = (event: globalThis.PointerEvent) => {
      // The scrollbar itself.
      if (event.target === box) userScrolled.current = performance.now();
    };
    box.addEventListener("wheel", onWheel, { passive: false });
    box.addEventListener("touchstart", onTouch, { passive: true });
    box.addEventListener("pointerdown", onPointer);
    return () => {
      box.removeEventListener("wheel", onWheel);
      box.removeEventListener("touchstart", onTouch);
      box.removeEventListener("pointerdown", onPointer);
    };
  }, [zoomBy]);

  // Follow the clock: move the playhead, and keep it in sight. Only when the
  // time moved: the same moment again means the lines changed under it, after
  // an arrangement made somewhere else on the timeline, which must stay in view.
  useEffect(() => {
    let last: number | null = null;
    return subscribe((seconds) => {
      place(seconds);
      const moved = seconds !== last;
      last = seconds;
      const box = scroller.current;
      if (!box || scrub.current || !moved) return;
      const x = seconds * view.current.pps;
      const left = box.scrollLeft;
      const seen = box.clientWidth;
      if (x >= left - 1 && x <= left + seen - 24) return;
      const now = performance.now();
      const moving = playingRef.current;
      // While playing, a person scrolling to look elsewhere is left alone for a moment.
      if (moving && now - userScrolled.current < 2500) return;
      if (now < autoUntil.current) return;
      const smooth = moving && !prefersReducedMotion();
      autoUntil.current = smooth ? now + 450 : 0;
      box.scrollTo({ left: Math.max(0, moving ? x - seen * 0.12 : x - seen / 2), behavior: smooth ? "smooth" : "auto" });
    });
  }, [subscribe, place]);

  const timeAt = (clientX: number) => {
    const box = content.current;
    if (!box) return 0;
    return (clientX - box.getBoundingClientRect().left) / view.current.pps;
  };

  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    // A clip selects its own line; this is the ruler, the voice track and the playhead.
    if (target.closest("[data-clip]")) return;
    const onHandle = Boolean(target.closest("[data-knob]"));
    if (event.pointerType === "touch" && !onHandle) {
      // A finger scrolls the timeline, so a touch seeks on a tap, not on the way down.
      scrub.current = { pointer: event.pointerId, touch: true, x: event.clientX, y: event.clientY };
      return;
    }
    event.preventDefault();
    if (onHandle) handle.current?.focus({ preventScroll: true });
    scrub.current = { pointer: event.pointerId, touch: false, x: event.clientX, y: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
    seek(timeAt(event.clientX));
  }

  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    const active = scrub.current;
    if (!active || active.touch || active.pointer !== event.pointerId) return;
    seek(timeAt(event.clientX));
  }

  function pointerUp(event: PointerEvent<HTMLDivElement>) {
    const active = scrub.current;
    scrub.current = null;
    if (!active || active.pointer !== event.pointerId) return;
    if (active.touch) {
      if (Math.hypot(event.clientX - active.x, event.clientY - active.y) < 8) seek(timeAt(event.clientX));
      return;
    }
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  function knobKey(event: KeyboardEvent<HTMLDivElement>) {
    const now = time();
    const big = event.shiftKey ? 5 : 1;
    const moves: Record<string, number> = {
      ArrowLeft: now - big,
      ArrowDown: now - big,
      ArrowRight: now + big,
      ArrowUp: now + big,
      PageDown: now - 10,
      PageUp: now + 10,
      Home: 0,
      End: duration,
    };
    if (event.key === " ") {
      event.preventDefault();
      event.stopPropagation();
      toggle();
      return;
    }
    if (!(event.key in moves) || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    event.stopPropagation();
    seek(moves[event.key]);
  }

  const zoomButton =
    "inline-flex h-7 min-w-7 items-center justify-center rounded-[var(--radius-control)] px-1.5 text-sm text-muted hover:bg-graphite hover:text-text disabled:cursor-not-allowed disabled:opacity-45";

  return (
    <div className="relative flex bg-graphite">
      <div aria-hidden className="w-16 shrink-0 border-r border-hairline bg-panel text-sm text-muted sm:w-[4.5rem]">
        <div className="border-b border-hairline" style={{ height: RULER }} />
        <div className="flex items-center px-3" style={{ height: IMAGES }}>
          Images
        </div>
        <div className="flex items-center px-3" style={{ height: VOICE }}>
          Voice
        </div>
      </div>

      <div
        ref={scroller}
        className="relative min-w-0 flex-1 overflow-x-scroll overflow-y-hidden overscroll-x-contain [scrollbar-color:var(--color-hairline)_transparent] [scrollbar-width:thin]"
      >
        <div
          ref={content}
          onPointerDown={pointerDown}
          onPointerMove={pointerMove}
          onPointerUp={pointerUp}
          onPointerCancel={() => {
            scrub.current = null;
          }}
          className="relative select-none"
          style={{ width }}
        >
          <Ruler pps={pps} duration={span} width={width} viewport={viewport} scroller={scroller} />
          <ClipTrack
            lines={lines}
            pps={pps}
            selected={selected}
            uploads={uploads}
            onSelect={onSelect}
            onOpen={onOpen}
            onFiles={onFiles}
            onNudge={onNudge}
          />
          {!lines.length ? (
            <p className="hatch-muted absolute inset-x-0 flex items-center px-3 text-sm text-muted" style={{ top: RULER, height: IMAGES }}>
              <span className="sticky left-3 bg-graphite px-1">The lines appear here once the narration is transcribed.</span>
            </p>
          ) : null}
          <Waveform
            url={peaks}
            pps={pps}
            duration={span}
            viewport={viewport}
            height={VOICE}
            scroller={scroller}
            subscribe={subscribe}
          />
          <div ref={playhead} className="pointer-events-none absolute inset-y-0 left-0 z-30 w-px bg-text will-change-transform">
            <div
              ref={handle}
              data-knob
              role="slider"
              tabIndex={0}
              aria-label="Playhead"
              aria-valuemin={0}
              aria-valuemax={Number(duration.toFixed(1))}
              aria-valuenow={0}
              aria-valuetext={`${timecode(0)} of ${timecode(duration)}`}
              aria-orientation="horizontal"
              onKeyDown={knobKey}
              className="pointer-events-auto absolute top-0 left-1/2 h-4 w-3.5 -translate-x-1/2 cursor-ew-resize touch-none bg-text [clip-path:polygon(0_0,100%_0,100%_62%,50%_100%,0_62%)] focus-visible:outline-none focus-visible:[clip-path:none] focus-visible:shadow-[0_0_0_2px_var(--color-graphite),0_0_0_4px_var(--color-text)]"
            />
          </div>
        </div>
      </div>

      <div
        className="absolute top-0 right-0 z-40 flex items-center gap-0.5 bg-panel pr-1 pl-1.5 shadow-[-14px_0_12px_var(--color-panel)]"
        style={{ height: RULER - 1 }}
      >
        <button type="button" className={zoomButton} aria-label="Zoom out" title="Zoom out (-)" disabled={fitting} onClick={() => zoomBy(1 / ZOOM_STEP)}>
          <Minus size={15} aria-hidden />
        </button>
        <button
          type="button"
          className={zoomButton}
          aria-label="Zoom in"
          title="Zoom in (+)"
          disabled={pps >= clampZoom(Infinity, fit) - 1e-6}
          onClick={() => zoomBy(ZOOM_STEP)}
        >
          <Plus size={15} aria-hidden />
        </button>
        <button
          type="button"
          className={zoomButton}
          aria-pressed={fitting}
          title="Show the whole narration"
          onClick={() => setZoom(null)}
        >
          Fit
        </button>
      </div>
    </div>
  );
}

type RulerProps = {
  pps: number;
  duration: number;
  width: number;
  viewport: number;
  scroller: RefObject<HTMLDivElement | null>;
};

/**
 * Minutes and seconds, as far apart as the zoom allows while keeping the
 * labels about 70 px apart. Only the ticks near the visible part are drawn,
 * so an hour of narration at full zoom is still a few dozen elements.
 */
const Ruler = memo(function Ruler({ pps, duration, width, viewport, scroller }: RulerProps) {
  const [left, setLeft] = useState(0);

  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    let frame = 0;
    const read = () => {
      frame = 0;
      setLeft(box.scrollLeft);
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(read);
    };
    box.addEventListener("scroll", onScroll, { passive: true });
    frame = window.requestAnimationFrame(read);
    return () => {
      box.removeEventListener("scroll", onScroll);
      window.cancelAnimationFrame(frame);
    };
  }, [scroller, pps]);

  const step = tickStep(pps);
  const minor = minorStep(step);
  const from = Math.max(0, (left - viewport) / pps);
  const to = Math.min(duration, (left + viewport * 2) / pps);
  const majors: number[] = [];
  for (let at = Math.floor(from / step) * step; at <= to; at += step) majors.push(at);
  const minors: number[] = [];
  if (minor * pps >= 6) {
    for (let at = Math.floor(from / minor) * minor; at <= to; at += minor) {
      const ratio = at / step;
      if (Math.abs(ratio - Math.round(ratio)) > 1e-6) minors.push(at);
    }
  }

  return (
    <div aria-hidden className="relative border-b border-hairline bg-panel" style={{ height: RULER, width }}>
      {minors.map((at) => (
        <span key={`m${at}`} className="absolute bottom-0 h-1.5 w-px bg-hairline" style={{ left: at * pps }} />
      ))}
      {majors.map((at) => (
        <span key={at} className="absolute bottom-0 h-full" style={{ left: at * pps }}>
          <span className="absolute bottom-0 left-0 h-2.5 w-px bg-muted/70" />
          {at * pps < width - 34 ? (
            <span className="timecode absolute top-1.5 left-1 text-xs leading-4 whitespace-nowrap text-muted">
              {clock(at)}
            </span>
          ) : null}
        </span>
      ))}
    </div>
  );
});
