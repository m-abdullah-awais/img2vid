"use client";

import { ImagePlus, LayoutGrid, List, ListOrdered } from "lucide-react";
import { memo, useCallback, useMemo, useRef } from "react";
import type { DropTarget } from "@/lib/arrange";
import type { Line, Project } from "@/lib/types";
import { Button } from "../ui/Button";
import { Segmented } from "../ui/Segmented";
import { GridView } from "./GridView";
import { LineRow, type RowHandlers } from "./LineRow";
import { UnplacedTray } from "./UnplacedTray";

export type Filter = "all" | "missing";
export type View = "list" | "grid";

type Props = Omit<RowHandlers, "onPick"> & {
  project: Project;
  filter: Filter;
  view: View;
  locked: boolean;
  lockedReason: string | null;
  uploads: Record<number, number>;
  /** The line selected in the editor, which follows the preview while it plays. */
  selectedLine: number | null;
  onFilter: (filter: Filter) => void;
  onView: (view: View) => void;
  onRenumber: () => void;
  onAddImages: () => void;
  onTranscribe: () => void;
  onUploadTranscript: () => void;
  onNarration: () => void;
  onRemoveImage: (name: string) => void;
  /** Narration is being transcribed for this project right now. */
  transcribing: boolean;
};

export const Storyboard = memo(function Storyboard({
  project,
  filter,
  view,
  locked,
  lockedReason,
  uploads,
  selectedLine,
  onFilter,
  onView,
  onRenumber,
  onAddImages,
  onTranscribe,
  onUploadTranscript,
  onNarration,
  onRemoveImage,
  transcribing,
  onOpen,
  onFiles,
  onNudge,
}: Props) {
  const lines = project.storyboard;
  const missingCount = project.images.missing.length;
  const total = lines.length;
  const picker = useRef<HTMLInputElement>(null);
  const pickLine = useRef<number | null>(null);

  const shown = useMemo<Line[]>(
    () => (filter === "missing" ? lines.filter((line) => line.state === "missing") : lines),
    [filter, lines],
  );

  const duplicates = useMemo(() => {
    const map = new Map<number, string[]>();
    for (const entry of project.images.duplicates) map.set(entry.line, entry.names);
    return map;
  }, [project.images.duplicates]);

  // One hidden file input serves every empty line's "Add image".
  const pick = useCallback(
    (line: number) => {
      if (locked) return;
      pickLine.current = line;
      picker.current?.click();
    },
    [locked],
  );

  const handlers = { onOpen, onPick: pick, onFiles, onNudge };

  return (
    <section aria-labelledby="storyboard-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 id="storyboard-title" className="heading text-2xl">
          Storyboard
        </h2>
        {total ? (
          <>
            <Segmented<Filter>
              label="Show"
              value={filter}
              onChange={onFilter}
              options={[
                { value: "all", label: <span className="timecode">All {total}</span> },
                {
                  value: "missing",
                  label: (
                    <span className={`timecode ${missingCount ? "text-missing" : ""}`}>Missing {missingCount}</span>
                  ),
                },
              ]}
            />
            <Segmented<View>
              label="View"
              value={view}
              onChange={onView}
              options={[
                {
                  value: "list",
                  label: (
                    <>
                      <List size={15} aria-hidden />
                      List
                    </>
                  ),
                },
                {
                  value: "grid",
                  label: (
                    <>
                      <LayoutGrid size={15} aria-hidden />
                      Grid
                    </>
                  ),
                },
              ]}
            />
          </>
        ) : null}
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:flex-1 sm:justify-end">
          <Button
            size="sm"
            variant="ghost"
            onClick={onRenumber}
            disabled={locked || project.images.total === 0}
            title={lockedReason ?? undefined}
          >
            <ListOrdered size={15} aria-hidden />
            Renumber
          </Button>
          <Button size="sm" variant="secondary" onClick={onAddImages} disabled={locked} title={lockedReason ?? undefined}>
            <ImagePlus size={15} aria-hidden />
            Add images
          </Button>
        </div>
      </div>

      {total ? (
        <p className="text-sm text-muted">
          Drag an image onto a line to move it there, or between two lines to insert it. Drop files from
          your computer onto a line the same way.
        </p>
      ) : null}

      <UnplacedTray
        images={project.images.unplaced}
        lines={total}
        base={project.images.base}
        hasTranscript={Boolean(project.transcript)}
        locked={locked}
        onRemove={onRemoveImage}
      />

      <input
        ref={picker}
        type="file"
        accept="image/*,.jpg,.jpeg,.png,.webp,.bmp,.gif,.tif,.tiff"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          const line = pickLine.current;
          event.target.value = "";
          if (file && line) onFiles([file], { op: "place", line } satisfies DropTarget);
        }}
      />

      {!total && transcribing ? (
        <div className="flex flex-col items-start gap-2 rounded-[var(--radius-control)] border border-dashed border-hairline px-5 py-8">
          <p className="heading text-xl">Transcribing narration</p>
          <p className="max-w-[62ch] text-sm text-muted">
            The lines appear here when it finishes. Its progress is at the bottom of the window.
          </p>
        </div>
      ) : !total ? (
        <div className="flex flex-col items-start gap-3 rounded-[var(--radius-control)] border border-dashed border-hairline px-5 py-8">
          <p className="heading text-xl">No lines yet</p>
          {project.audio.files.length ? (
            <>
              <p className="max-w-[62ch] text-sm text-muted">
                Each transcript line gets one image, so the storyboard appears once there is a transcript.
                Transcribe the narration, or upload a transcript you already have.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="primary" onClick={onTranscribe}>
                  Transcribe
                </Button>
                <Button size="sm" variant="secondary" onClick={onUploadTranscript}>
                  Upload transcript
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="max-w-[62ch] text-sm text-muted">
                Start with the narration. Once it is transcribed, every line of it appears here waiting for
                its image.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="primary" onClick={onNarration}>
                  Upload narration
                </Button>
                <Button size="sm" variant="secondary" onClick={onUploadTranscript}>
                  Upload transcript
                </Button>
              </div>
            </>
          )}
        </div>
      ) : shown.length === 0 ? (
        <div className="flex flex-col items-start gap-2 rounded-[var(--radius-control)] border border-hairline px-5 py-6">
          <p className="flex items-center gap-2 font-semibold">
            <span aria-hidden className="h-2 w-2 rounded-full bg-ready" />
            Every line has an image
          </p>
          <Button size="sm" variant="ghost" onClick={() => onFilter("all")}>
            Show all {total} lines
          </Button>
        </div>
      ) : view === "list" ? (
        <div role="list" aria-label="Storyboard" className="flex flex-col">
          {shown.map((line) => (
            <LineRow
              key={line.line}
              line={line}
              total={total}
              locked={locked}
              duplicateNames={duplicates.get(line.line) ?? null}
              progress={uploads[line.line] ?? null}
              selected={line.line === selectedLine}
              {...handlers}
            />
          ))}
        </div>
      ) : (
        <GridView
          lines={shown}
          total={total}
          locked={locked}
          uploads={uploads}
          selectedLine={selectedLine}
          {...handlers}
        />
      )}
    </section>
  );
});
