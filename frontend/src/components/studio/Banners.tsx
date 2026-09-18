"use client";

import { memo, type ReactNode } from "react";
import type { Project } from "@/lib/types";
import { Button } from "../ui/Button";

type Tone = "attention" | "error" | "info";

const edges: Record<Tone, string> = {
  attention: "border-missing",
  error: "border-build",
  info: "border-muted",
};

export function Banner({
  tone,
  title,
  children,
  actions,
}: {
  tone: Tone;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex flex-col gap-3 border-l-2 bg-panel px-4 py-3 sm:flex-row sm:items-start ${edges[tone]}`}
    >
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-semibold">{title}</p>
        {children ? <div className="mt-0.5 max-w-[92ch] text-muted">{children}</div> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

type Props = {
  project: Project;
  lockedReason: string | null;
  onRenumber: () => void;
  onTranscribe: () => void;
  busy: string | null;
};

/** Every state in the snapshot that can put an image on the wrong line, said plainly. */
export const Banners = memo(function Banners({ project, lockedReason, onRenumber, onTranscribe, busy }: Props) {
  const { images, transcript } = project;
  const lines = project.storyboard.length;
  const banners: ReactNode[] = [];

  if (lockedReason) {
    banners.push(
      <Banner key="locked" tone="info" title="Changes are paused while the engine works on this project">
        {lockedReason}
      </Banner>,
    );
  }

  if (images.mode === "positional" && images.reason) {
    const { kind, name, number } = images.reason;
    const quoted = name ? `"${name}"` : "One image";
    let body: string;
    if (kind === "unnumbered") {
      body = `${quoted} does not start with a number, so the images are paired with lines in name order instead of by number. One missing image would push every image after it onto the wrong line.`;
    } else if (kind === "past_end") {
      body = `${quoted} starts with ${number ?? "a number"}, past the last line (${lines}), so the images are paired with lines in name order instead of by number. Camera names do this. One missing image would push every image after it onto the wrong line.`;
    } else {
      body = "There is no transcript yet, so the images are waiting in name order. Once there is one, each numbered image goes on the line its number names.";
    }
    banners.push(
      <Banner
        key="positional"
        tone="attention"
        title="Images are paired by position, not by number"
        actions={
          kind !== "no_lines" ? (
            <Button size="sm" variant="secondary" onClick={onRenumber} disabled={project.locked.images}>
              Renumber images
            </Button>
          ) : null
        }
      >
        {body} Renumbering gives each image a number in its current order, so its line is fixed from then on.
      </Banner>,
    );
  }

  if (images.duplicates.length) {
    const count = images.duplicates.length;
    banners.push(
      <Banner
        key="duplicates"
        tone="error"
        title={count === 1 ? `Two images claim line ${images.duplicates[0].line}` : `${count} lines are claimed by more than one image`}
      >
        <ul className="flex flex-col gap-0.5">
          {images.duplicates.map((entry) => (
            <li key={entry.line}>
              <span className="timecode text-text">Line {entry.line}</span>: {entry.names.join(", ")}
            </li>
          ))}
        </ul>
        <p className="mt-1">
          Keep one image on each line: move or remove the others. The video cannot be built until then.
        </p>
      </Banner>,
    );
  }

  if (transcript?.stale) {
    banners.push(
      <Banner
        key="stale"
        tone="attention"
        title="The narration changed after this transcript was made"
        actions={
          <Button size="sm" variant="secondary" onClick={onTranscribe} disabled={Boolean(busy) || project.locked.transcript} title={busy ?? undefined}>
            Transcribe again
          </Button>
        }
      >
        The line timings may no longer match the audio. Transcribe again, or upload a transcript made
        from the new narration.
      </Banner>,
    );
  }

  if (!banners.length) return null;
  return <div className="flex flex-col gap-2">{banners}</div>;
});
