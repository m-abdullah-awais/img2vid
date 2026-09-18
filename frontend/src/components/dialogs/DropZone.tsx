"use client";

import { Upload } from "lucide-react";
import { useId, useRef, useState, type DragEvent, type ReactNode } from "react";
import { bytes } from "@/lib/format";
import { ProgressBar } from "../ui/ProgressBar";

type Props = {
  accept: string;
  multiple?: boolean;
  disabled?: boolean;
  onFiles: (files: File[]) => void;
  title: ReactNode;
  hint?: ReactNode;
};

/** Drop files here, or press it to choose them. */
export function DropZone({ accept, multiple = false, disabled = false, onFiles, title, hint }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const depth = useRef(0);
  const hintId = useId();

  const has = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes("Files");

  return (
    <div
      onDragEnter={(event) => {
        if (!has(event) || disabled) return;
        event.preventDefault();
        depth.current += 1;
        setOver(true);
      }}
      onDragOver={(event) => {
        if (!has(event) || disabled) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      }}
      onDragLeave={() => {
        depth.current = Math.max(0, depth.current - 1);
        if (depth.current === 0) setOver(false);
      }}
      onDrop={(event) => {
        if (!has(event) || disabled) return;
        event.preventDefault();
        depth.current = 0;
        setOver(false);
        const files = Array.from(event.dataTransfer.files || []);
        if (files.length) onFiles(multiple ? files : files.slice(0, 1));
      }}
      className={`motion-drop rounded-[var(--radius-control)] border border-dashed ${
        over ? "border-text bg-graphite" : "border-hairline"
      }`}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        aria-describedby={hint ? hintId : undefined}
        className="flex w-full flex-col items-center gap-1.5 rounded-[var(--radius-control)] px-4 py-7 text-center disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Upload size={20} aria-hidden className="text-muted" />
        <span className="font-semibold">{over ? "Drop to add" : title}</span>
        {hint ? (
          <span id={hintId} className="max-w-[52ch] text-xs text-muted">
            {hint}
          </span>
        ) : null}
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(event) => {
          const files = Array.from(event.target.files || []);
          event.target.value = "";
          if (files.length) onFiles(files);
        }}
      />
    </div>
  );
}

export type UploadStatus = "waiting" | "uploading" | "done" | "failed" | "exists";

export type UploadItem = {
  file: File;
  progress: number;
  status: UploadStatus;
  message?: string;
};

const statusWords: Record<UploadStatus, string> = {
  waiting: "Waiting",
  uploading: "Uploading",
  done: "Uploaded",
  failed: "Not uploaded",
  exists: "Name already used",
};

/** Files queued or on their way, each with its own bar. */
export function UploadList({ items, numbered = false }: { items: UploadItem[]; numbered?: boolean }) {
  if (!items.length) return null;
  return (
    <ol className="max-h-[38vh] divide-y divide-hairline overflow-y-auto rounded-[var(--radius-control)] border border-hairline">
      {items.map((item, index) => (
        <li key={`${item.file.name}-${index}`} className="flex flex-col gap-1.5 px-3 py-2">
          <div className="flex items-baseline gap-3 text-sm">
            {numbered ? <span className="timecode w-6 text-muted">{index + 1}</span> : null}
            <span className="min-w-0 flex-1 truncate" title={item.file.name}>
              {item.file.name}
            </span>
            <span className="timecode text-xs text-muted">{bytes(item.file.size)}</span>
            <span
              className={`w-32 text-right text-xs ${
                item.status === "failed"
                  ? "text-text"
                  : item.status === "exists"
                    ? "text-missing"
                    : item.status === "done"
                      ? "text-ready"
                      : "text-muted"
              }`}
            >
              {statusWords[item.status]}
            </span>
          </div>
          {item.status === "uploading" || item.status === "done" ? (
            <ProgressBar
              value={item.progress}
              thin
              tone={item.status === "done" ? "ready" : "text"}
              label={`${item.file.name}, ${statusWords[item.status]}`}
            />
          ) : null}
          {item.message ? (
            <p className="flex items-start gap-1.5 text-xs text-muted">
              {item.status === "failed" ? <span aria-hidden className="mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full bg-build" /> : null}
              {item.message}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
