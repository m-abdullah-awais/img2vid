"use client";

import { ImagePlus, Replace, Trash2 } from "lucide-react";
import { useId, useRef, useState, type FormEvent } from "react";
import { describeDrop } from "@/lib/arrange";
import { bytes, pad, shortSeconds, timecode } from "@/lib/format";
import type { ImageRef, Line, Project } from "@/lib/types";
import { Banner } from "../studio/Banners";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Field, TextInput } from "../ui/Field";
import { Thumb, thumbAt } from "../ui/Thumb";

type Props = {
  project: Project;
  line: number;
  locked: boolean;
  lockedReason: string | null;
  onClose: () => void;
  onReplace: (file: File, line: number) => void;
  onRemove: (name: string) => void;
  onMove: (image: string, fromLine: number, toLine: number) => void;
};

/** One line's image, larger: replace it, remove it, or move it to another line. */
export function ImageDialog({ project, line, locked, lockedReason, onClose, onReplace, onRemove, onMove }: Props) {
  const slot = project.storyboard[line - 1];
  const total = project.storyboard.length;

  if (!slot) return null;
  const image = slot.image;
  const duplicates = project.images.duplicates.find((entry) => entry.line === line)?.names ?? null;

  return (
    <Dialog
      title={`Line ${pad(line, Math.max(3, String(total).length))}`}
      size="lg"
      onClose={onClose}
      description={
        <span className="timecode">
          {timecode(slot.start)} to {timecode(slot.end)}, on screen for {shortSeconds(slot.seconds)}
        </span>
      }
    >
      <div className="flex flex-col gap-4">
        {locked ? <Banner tone="info" title="Images are locked">{lockedReason}</Banner> : null}
        <p className="max-w-[70ch] text-base">{slot.text}</p>

        {image ? (
          <div className="overflow-hidden rounded-[var(--radius-frame)] border border-hairline bg-graphite">
            <Thumb src={thumbAt(image.thumb, 640)} alt={`The image on line ${line}`} eager fit="contain" className="aspect-video w-full" />
          </div>
        ) : (
          <div className="hatch flex aspect-video w-full items-center justify-center rounded-[var(--radius-frame)]">
            <span className="rounded-[var(--radius-control)] bg-graphite/90 px-3 py-1 text-sm">This line has no image yet</span>
          </div>
        )}

        {image ? (
          <p className="text-sm text-muted">
            <span className="text-text">{image.name}</span>
            <span className="timecode ml-3">{bytes(image.bytes)}</span>
          </p>
        ) : null}
        {duplicates ? (
          <Banner tone="error" title="More than one image claims this line">
            {duplicates.join(", ")}. Keep one: move or remove the others.
          </Banner>
        ) : null}

        <ImageActions line={line} image={image} locked={locked} onReplace={onReplace} onRemove={onRemove} onDone={onClose} />
        {image ? (
          <p className="text-xs text-muted">
            A replaced or removed image goes to the trash, and the message that follows offers Undo.
          </p>
        ) : null}

        {image ? (
          <MoveToLine
            lines={project.storyboard}
            line={line}
            image={image}
            locked={locked}
            onMove={onMove}
            onDone={onClose}
            className="border-t border-hairline pt-4"
          />
        ) : null}
      </div>
    </Dialog>
  );
}

type ActionsProps = {
  line: number;
  image: ImageRef | null;
  locked: boolean;
  onReplace: (file: File, line: number) => void;
  onRemove: (name: string) => void;
  /** After either one has been asked for, such as closing the dialog. */
  onDone?: () => void;
  /** "Replace" and "Remove", for a narrow column where the image is plainly the subject. */
  short?: boolean;
};

/**
 * Replace or add the image on a line, and remove it. The dialog and the
 * editor's inspector both show these, over the same studio actions.
 */
export function ImageActions({ line, image, locked, onReplace, onRemove, onDone, short = false }: ActionsProps) {
  const picker = useRef<HTMLInputElement>(null);
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="secondary"
        size="sm"
        disabled={locked}
        onClick={() => picker.current?.click()}
        aria-label={image ? `Replace the image on line ${line}` : `Add an image to line ${line}`}
      >
        {image ? <Replace size={15} aria-hidden /> : <ImagePlus size={15} aria-hidden />}
        {image ? (short ? "Replace" : "Replace image") : "Add image"}
      </Button>
      {image ? (
        <Button
          variant="secondary"
          size="sm"
          disabled={locked}
          aria-label={`Remove ${image.name}`}
          onClick={() => {
            onRemove(image.name);
            onDone?.();
          }}
        >
          <Trash2 size={15} aria-hidden />
          {short ? "Remove" : "Remove image"}
        </Button>
      ) : null}
      <input
        ref={picker}
        type="file"
        accept="image/*,.jpg,.jpeg,.png,.webp,.bmp,.gif,.tif,.tiff"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) {
            onReplace(file, line);
            onDone?.();
          }
        }}
      />
    </div>
  );
}

type MoveProps = {
  lines: Line[];
  line: number;
  image: ImageRef;
  locked: boolean;
  onMove: (image: string, fromLine: number, toLine: number) => void;
  onDone?: () => void;
  className?: string;
  /** Label, field and button on one row, for the editor's inspector. */
  compact?: boolean;
};

/** Move a line's image to another line by its number, saying first what that would do. */
export function MoveToLine({ lines, line, image, locked, onMove, onDone, className = "", compact = false }: MoveProps) {
  const [target, setTarget] = useState("");
  const fieldId = useId();
  const total = lines.length;
  const wanted = Number(target);
  const valid = Number.isInteger(wanted) && wanted >= 1 && wanted <= total && wanted !== line;
  const outcome = valid
    ? describeDrop(lines, { image: image.name, thumb: image.thumb, fromLine: line }, { op: "place", line: wanted })
    : null;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || !outcome?.allowed) return;
    onMove(image.name, line, wanted);
    setTarget("");
    onDone?.();
  }

  if (compact) {
    return (
      <form className={`flex flex-col gap-1 ${className}`} onSubmit={submit}>
        <div className="flex items-center gap-2">
          <label htmlFor={fieldId} className="text-sm font-medium whitespace-nowrap">
            Move to line
          </label>
          <input
            id={fieldId}
            aria-describedby={`${fieldId}-hint`}
            type="number"
            inputMode="numeric"
            min={1}
            max={total}
            value={target}
            disabled={locked}
            onChange={(event) => setTarget(event.target.value)}
            className="timecode h-8 w-16 rounded-[var(--radius-control)] border border-hairline bg-graphite px-2 text-sm text-text hover:border-muted focus-visible:border-text disabled:opacity-50"
          />
          <Button type="submit" size="sm" variant="secondary" disabled={locked || !valid || !outcome?.allowed}>
            Move
          </Button>
        </div>
        <p id={`${fieldId}-hint`} className="text-xs text-muted">
          {outcome ? outcome.label : `A line from 1 to ${total}.`}
        </p>
      </form>
    );
  }

  return (
    <form className={`flex flex-wrap items-end gap-3 ${className}`} onSubmit={submit}>
      <Field label="Move to line" hint={outcome ? outcome.label : `A line from 1 to ${total}.`}>
        {({ id, describedBy }) => (
          <TextInput
            id={id}
            aria-describedby={describedBy}
            type="number"
            inputMode="numeric"
            min={1}
            max={total}
            value={target}
            disabled={locked}
            onChange={(event) => setTarget(event.target.value)}
            className="timecode w-28"
          />
        )}
      </Field>
      <Button type="submit" variant="secondary" disabled={locked || !valid || !outcome?.allowed} className="mb-[22px]">
        Move
      </Button>
    </form>
  );
}
