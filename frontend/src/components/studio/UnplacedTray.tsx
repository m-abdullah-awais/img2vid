"use client";

import { Trash2 } from "lucide-react";
import { memo } from "react";
import { leadingNumber } from "@/lib/format";
import type { ImageRef } from "@/lib/types";
import { IconButton } from "../ui/Button";
import { Thumb } from "../ui/Thumb";
import { DragHandle } from "./targets";

type Props = {
  images: ImageRef[];
  lines: number;
  base: 0 | 1;
  hasTranscript: boolean;
  locked: boolean;
  onRemove: (name: string) => void;
};

/** Why one image is on no line, in a few words under it. */
function reasonFor(name: string, lines: number, base: 0 | 1, hasTranscript: boolean): string {
  if (!hasTranscript) return "Waiting for a transcript";
  const number = leadingNumber(name);
  if (number === null) return "No number in its name";
  const line = number - base + 1;
  if (line > lines) return "Past the last line";
  if (line >= 1) return `Line ${line} is taken`;
  return "Before the first line";
}

/**
 * Images on no line: numbered past the end, sharing a line another image
 * already claims, or waiting for a transcript. Drag one onto a line to place it.
 */
export const UnplacedTray = memo(function UnplacedTray({ images, lines, base, hasTranscript, locked, onRemove }: Props) {
  if (!images.length) return null;
  const explain = !hasTranscript
    ? "There is no transcript yet, so no image has a line. Transcribe the narration or upload a transcript, and each image goes on the line its number names."
    : `An image waits here when its number is past the last line, ${lines}, or when another image already claims its line. Drag one onto a line to place it there, or remove it.`;
  return (
    <section aria-labelledby="unplaced-title" className="rounded-[var(--radius-control)] border border-hairline bg-panel px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h3 id="unplaced-title" className="heading text-xl">
          Unplaced
        </h3>
        <span className="timecode text-sm text-muted">{images.length === 1 ? "1 image" : `${images.length} images`}</span>
      </div>
      <p className="mt-0.5 max-w-[80ch] text-sm text-muted">{explain}</p>
      <ul className="mt-3 flex flex-wrap gap-3">
        {images.map((image) => {
          const why = reasonFor(image.name, lines, base, hasTranscript);
          return (
            <li key={image.name} className="flex w-32 flex-col gap-1">
              <DragHandle
                source={{ image: image.name, thumb: image.thumb, fromLine: null }}
                label={`${image.name}, unplaced: ${why}. Press Space to move it onto a line.`}
                className="aspect-video w-32 border border-hairline"
              >
                <Thumb src={image.thumb} alt="" className="h-full w-full" />
              </DragHandle>
              <div className="flex items-start gap-1">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs" title={image.name}>
                    {image.name}
                  </p>
                  <p className="truncate text-xs text-muted">{why}</p>
                </div>
                <IconButton label={`Remove ${image.name}`} disabled={locked} onClick={() => onRemove(image.name)}>
                  <Trash2 size={14} aria-hidden />
                </IconButton>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
});
