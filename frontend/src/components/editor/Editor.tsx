"use client";

import { AudioLines } from "lucide-react";
import { useCallback, useLayoutEffect, useMemo, useRef } from "react";
import type { DropTarget } from "@/lib/arrange";
import { onScreenFrom } from "@/lib/timeline";
import type { Project } from "@/lib/types";
import { useJobFinished, useRunning } from "../job/JobProvider";
import { Button } from "../ui/Button";
import { Inspector } from "./Inspector";
import { PreviewStage } from "./PreviewStage";
import { Timeline, type TimelineHandle } from "./Timeline";
import { Transport, useEditorKeys } from "./Transport";
import type { ArrangeHistory } from "./useArrangeHistory";
import type { Playback } from "./usePlayback";

type Props = {
  project: Project;
  playback: Playback;
  history: ArrangeHistory;
  /** Images are locked by a job, so nothing can be arranged. */
  locked: boolean;
  lockedReason: string | null;
  uploads: Record<number, number>;
  onOpen: (line: number) => void;
  onFiles: (files: File[], target: DropTarget) => void;
  onNudge: (line: number, delta: -1 | 1) => void;
  onMove: (image: string, fromLine: number, toLine: number) => void;
  onReplace: (file: File, line: number) => void;
  onRemove: (name: string) => void;
  onShowInStoryboard: (line: number) => void;
  onNarration: () => void;
};

/**
 * The video, watched while it is arranged. The browser plays the narration
 * and shows each line's image as it is spoken; nothing is rendered, so it
 * costs a running build nothing and works while one runs.
 */
export function Editor({
  project,
  playback,
  history,
  locked,
  lockedReason,
  uploads,
  onOpen,
  onFiles,
  onNudge,
  onMove,
  onReplace,
  onRemove,
  onShowInStoryboard,
  onNarration,
}: Props) {
  const lines = project.storyboard;
  const total = lines.length;
  const timeline = useRef<TimelineHandle>(null);
  const running = useRunning();
  const { line, status, seekLine, seek, toggle, retry, duration } = playback;
  const current = line !== null ? (lines[line - 1] ?? null) : null;
  const from = line !== null ? onScreenFrom(lines, line - 1) : 0;
  const hasNarration = Boolean(project.audio.preview);

  // The joined narration is not made while a job runs; ask again once it ends.
  useJobFinished(() => {
    if (status === "failed") retry();
  });

  const previous = useCallback(() => {
    if (line !== null && line > 1) seekLine(line - 1);
  }, [line, seekLine]);
  const next = useCallback(() => {
    if (line !== null && line < total) seekLine(line + 1);
  }, [line, total, seekLine]);

  // Undo and redo work with or without narration; the rest need the preview.
  useEditorKeys({
    toggle: hasNarration ? toggle : null,
    previous: hasNarration ? previous : null,
    next: hasNarration ? next : null,
    undo: () => {
      if (!locked) void history.undo();
    },
    redo: () => {
      if (!locked) void history.redo();
    },
    zoomIn: hasNarration ? () => timeline.current?.zoomIn() : null,
    zoomOut: hasNarration ? () => timeline.current?.zoomOut() : null,
    start: hasNarration ? () => seek(0) : null,
    end: hasNarration ? () => seek(duration) : null,
  });

  const duplicates = useMemo(() => {
    const map = new Map<number, string[]>();
    for (const entry of project.images.duplicates) map.set(entry.line, entry.names);
    return map;
  }, [project.images.duplicates]);

  // On a wide screen the stage takes the height left once everything above
  // the editor and the editor's own controls are counted, so the stage, the
  // transport and the whole timeline fit in the window together. What is
  // above changes (a status line wraps, the job dock opens), so it is
  // measured rather than guessed.
  const frame = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const section = frame.current;
    if (!section) return;
    const fit = () => {
      const well = section.querySelector<HTMLElement>("[data-well]");
      if (!well) return;
      const dock = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--dock-h")) || 0;
      const top = section.getBoundingClientRect().top + window.scrollY;
      const controls = section.offsetHeight - well.offsetHeight;
      const room = window.innerHeight - dock - top - controls - 12;
      const height = `${Math.round(Math.min(760, Math.max(240, room)))}px`;
      if (section.style.getPropertyValue("--stage-h") !== height) section.style.setProperty("--stage-h", height);
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(document.querySelector("main") ?? document.body);
    window.addEventListener("resize", fit);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", fit);
    };
  }, [hasNarration]);

  if (!hasNarration) {
    return (
      <section
        aria-labelledby="editor-empty-title"
        className="flex flex-col items-start gap-3 rounded-[var(--radius-control)] border border-dashed border-hairline px-5 py-6"
      >
        <h2 id="editor-empty-title" className="heading text-xl">
          Add the narration to preview the video
        </h2>
        <p className="max-w-[62ch] text-sm text-muted">
          The preview plays the narration and shows each line&apos;s image as it is spoken, so you watch the video
          while you arrange it. Nothing is rendered until you build.
        </p>
        <Button size="sm" variant="secondary" onClick={onNarration}>
          <AudioLines size={15} aria-hidden />
          Upload narration
        </Button>
      </section>
    );
  }

  const problem =
    status === "failed"
      ? running.kind
        ? "The narration for the preview is made once the running job finishes."
        : "The narration could not be loaded for the preview."
      : null;

  return (
    <section
      ref={frame}
      aria-label="Preview and timeline"
      className="overflow-hidden rounded-[var(--radius-control)] border border-hairline bg-panel [--stage-h:clamp(240px,calc(100dvh-560px),760px)]"
    >
      <div className="grid lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col">
          <PreviewStage
            line={current}
            settings={project.settings}
            note={total ? null : "Each line's image appears here once the narration is transcribed."}
            onToggle={toggle}
          />
          <p className="flex h-14 items-center justify-center bg-graphite px-4 text-center">
            <span className="line-clamp-2 max-w-[72ch] text-base leading-snug">{current?.text ?? ""}</span>
          </p>
          <Transport
            playing={playback.playing}
            status={status}
            duration={duration}
            line={line}
            total={total}
            missing={current?.state === "missing"}
            problem={problem}
            subscribe={playback.subscribe}
            onToggle={toggle}
            onPrevious={previous}
            onNext={next}
            onRetry={problem && !running.kind ? retry : null}
            history={history}
            locked={locked}
          />
        </div>

        <aside
          aria-label="Selected line"
          className="relative border-hairline max-lg:order-last max-lg:border-t lg:border-l"
        >
          <div className="[scrollbar-color:var(--color-hairline)_transparent] [scrollbar-width:thin] lg:absolute lg:inset-0 lg:overflow-y-auto">
            <Inspector
              line={current}
              lines={lines}
              from={from}
              duplicateNames={current ? (duplicates.get(current.line) ?? null) : null}
              locked={locked}
              lockedReason={lockedReason}
              onReplace={onReplace}
              onRemove={onRemove}
              onMove={onMove}
              onFiles={onFiles}
              onShowInStoryboard={onShowInStoryboard}
            />
          </div>
        </aside>

        <div className="border-t border-hairline lg:col-span-2">
          <Timeline
            ref={timeline}
            lines={lines}
            duration={duration}
            selected={line}
            playing={playback.playing}
            playback={playback}
            peaks={project.audio.peaks}
            uploads={uploads}
            onSelect={seekLine}
            onOpen={onOpen}
            onFiles={onFiles}
            onNudge={onNudge}
          />
        </div>
      </div>
    </section>
  );
}
