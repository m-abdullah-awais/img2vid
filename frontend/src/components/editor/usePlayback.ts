"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiUrl } from "@/lib/api";
import { lineIndexAt, onScreenFrom, stageSrc } from "@/lib/timeline";
import type { Line } from "@/lib/types";

// The preview's clock is the narration itself, played by one <audio> element
// that is never put on the page. Every animation frame while it plays reads
// its currentTime and hands it to whoever subscribed (the playhead, the time
// readout, the waveform), which update the DOM through refs. React state
// changes only when the line on screen changes, so a 170 line storyboard is
// rendered again every few seconds at most, never 60 times a second.

export type AudioStatus = "none" | "loading" | "ready" | "failed";

export type Playback = {
  playing: boolean;
  /** The line on screen, 1-based, or null when there are no lines. */
  line: number | null;
  /** Seconds of narration, which is the length of the video. */
  duration: number;
  status: AudioStatus;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (seconds: number) => void;
  /** Go to the moment a line's image comes on screen, and show that line. */
  seekLine: (line: number) => void;
  /** Called with the time on every frame while playing and once per seek. Returns the unsubscribe. */
  subscribe: (listener: (seconds: number) => void) => () => void;
  /** The time now. For event handlers, not for rendering. */
  time: () => number;
  /** Ask for the narration again after it would not load. */
  retry: () => void;
};

type Options = {
  /** project.audio.preview, or null when there is no narration. */
  src: string | null;
  lines: Line[];
  /** project.audio.seconds. */
  seconds: number | null;
};

type Media = { src: string | null; status: AudioStatus; duration: number | null };

const PRELOAD_AHEAD = 2;

export function usePlayback({ src, lines, seconds }: Options): Playback {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timeRef = useRef(0);
  const indexRef = useRef(lines.length ? 0 : -1);
  const linesRef = useRef(lines);
  const durationRef = useRef(0);
  /** A time asked for before the audio could take it. */
  const pendingRef = useRef<number | null>(null);
  /** seekLine names its line outright, so a line with no length can still be shown. */
  const forcedRef = useRef<number | null>(null);
  const listeners = useRef(new Set<(seconds: number) => void>());
  const preloaded = useRef(new Set<string>());

  const [line, setLine] = useState<number | null>(lines.length ? 1 : null);
  const [media, setMedia] = useState<Media>({ src: null, status: "none", duration: null });
  const [playingSrc, setPlayingSrc] = useState<string | null>(null);

  const status: AudioStatus = !src ? "none" : media.src === src ? media.status : "loading";
  const playing = src !== null && playingSrc === src;
  const lastEnd = lines.length ? lines[lines.length - 1].end : 0;
  const duration = seconds ?? (media.src === src ? media.duration : null) ?? lastEnd;

  const emit = useCallback((time: number) => {
    const all = linesRef.current;
    const forced = forcedRef.current;
    forcedRef.current = null;
    const index = forced !== null && forced < all.length ? forced : lineIndexAt(all, time);
    if (index !== indexRef.current) {
      indexRef.current = index;
      setLine(index >= 0 ? index + 1 : null);
    }
    listeners.current.forEach((listener) => listener(time));
  }, []);

  useEffect(() => {
    durationRef.current = duration;
  }, [duration]);

  // New lines (an arrangement, a new transcript) can put a different line
  // under the same moment. Worked out on the next frame, not during render.
  useEffect(() => {
    linesRef.current = lines;
    const frame = window.requestAnimationFrame(() => emit(timeRef.current));
    return () => window.cancelAnimationFrame(frame);
  }, [lines, emit]);

  useEffect(() => {
    if (!src) return;
    const audio = new Audio();
    audio.preload = "auto";
    audioRef.current = audio;
    timeRef.current = 0;
    let frame = 0;

    const step = () => {
      frame = 0;
      if (audio.paused) return;
      timeRef.current = audio.currentTime;
      emit(timeRef.current);
      frame = window.requestAnimationFrame(step);
    };
    const known = () => (Number.isFinite(audio.duration) ? audio.duration : null);
    const onReady = () => {
      if (pendingRef.current !== null) {
        audio.currentTime = pendingRef.current;
        pendingRef.current = null;
      }
      setMedia({ src, status: "ready", duration: known() });
    };
    const onPlay = () => {
      setPlayingSrc(src);
      if (!frame) frame = window.requestAnimationFrame(step);
    };
    const onPause = () => {
      setPlayingSrc(null);
      window.cancelAnimationFrame(frame);
      frame = 0;
      timeRef.current = audio.currentTime;
      emit(timeRef.current);
    };
    const onError = () => {
      setPlayingSrc(null);
      setMedia({ src, status: "failed", duration: known() });
    };

    audio.addEventListener("loadedmetadata", onReady);
    audio.addEventListener("durationchange", onReady);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onPause);
    audio.addEventListener("error", onError);
    audio.src = apiUrl(src);
    const first = window.requestAnimationFrame(() => emit(0));

    return () => {
      window.cancelAnimationFrame(first);
      window.cancelAnimationFrame(frame);
      audio.removeEventListener("loadedmetadata", onReady);
      audio.removeEventListener("durationchange", onReady);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onPause);
      audio.removeEventListener("error", onError);
      audio.pause();
      // Let go of the file, so a narration being replaced is not held open.
      audio.removeAttribute("src");
      audio.load();
      if (audioRef.current === audio) audioRef.current = null;
    };
  }, [src, emit]);

  // The next two lines' images, fetched ahead so a cut never waits on the network.
  useEffect(() => {
    if (line === null) return;
    for (let ahead = 0; ahead < PRELOAD_AHEAD; ahead += 1) {
      const image = lines[line + ahead]?.image;
      if (!image) continue;
      const url = apiUrl(stageSrc(image));
      if (preloaded.current.has(url)) continue;
      if (preloaded.current.size > 400) preloaded.current.clear();
      preloaded.current.add(url);
      const loader = new Image();
      loader.decoding = "async";
      loader.src = url;
    }
  }, [line, lines]);

  const seek = useCallback(
    (seconds: number) => {
      const end = durationRef.current;
      const time = Math.max(0, end > 0 ? Math.min(seconds, end) : seconds);
      timeRef.current = time;
      const audio = audioRef.current;
      if (audio) {
        if (audio.readyState >= 1) audio.currentTime = time;
        else pendingRef.current = time;
      }
      emit(time);
    },
    [emit],
  );

  const seekLine = useCallback(
    (target: number) => {
      const all = linesRef.current;
      if (target < 1 || target > all.length) return;
      forcedRef.current = target - 1;
      seek(onScreenFrom(all, target - 1));
    },
    [seek],
  );

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.ended || timeRef.current >= durationRef.current - 0.02) seek(0);
    audio.play().catch((error: unknown) => {
      // AbortError means a pause came first, which is what was wanted.
      if (error instanceof DOMException && error.name === "AbortError") return;
      setMedia((current) => ({ src: current.src ?? null, status: "failed", duration: current.duration }));
    });
  }, [seek]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
  }, []);

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) play();
    else audio.pause();
  }, [play]);

  const subscribe = useCallback((listener: (seconds: number) => void) => {
    listeners.current.add(listener);
    listener(timeRef.current);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const time = useCallback(() => timeRef.current, []);

  const retry = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    pendingRef.current = timeRef.current;
    setMedia((current) => ({ ...current, status: "loading" }));
    audio.load();
  }, []);

  const safeLine = line !== null && line <= lines.length ? line : lines.length ? 1 : null;

  return useMemo(
    () => ({
      playing,
      line: safeLine,
      duration,
      status,
      play,
      pause,
      toggle,
      seek,
      seekLine,
      subscribe,
      time,
      retry,
    }),
    [playing, safeLine, duration, status, play, pause, toggle, seek, seekLine, subscribe, time, retry],
  );
}
