"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { pool, projectPath, toApiError, upload } from "@/lib/api";
import { bytes, clock, naturalCompare } from "@/lib/format";
import type { Project, ProjectEnvelope } from "@/lib/types";
import { Banner } from "../studio/Banners";
import { Button, IconButton } from "../ui/Button";
import { Checkbox } from "../ui/Field";
import { Dialog } from "../ui/Dialog";
import { useToast } from "../ui/Toast";
import { DropZone, UploadList, type UploadItem } from "./DropZone";

type Props = {
  project: Project;
  locked: boolean;
  lockedReason: string | null;
  onClose: () => void;
  onProject: (project: Project) => void;
  refetch: () => Promise<void>;
  onRemove: (name: string) => Promise<void>;
};

const ACCEPT = "audio/*,.wav,.mp3,.m4a,.aac,.flac,.ogg,.opus,.wma";

/** Pick or drop the narration. Several files are joined in name order. */
export function UploadNarrationDialog({ project, locked, lockedReason, onClose, onProject, refetch, onRemove }: Props) {
  const { toast } = useToast();
  const [items, setItems] = useState<UploadItem[]>([]);
  const [replace, setReplace] = useState(false);
  const [running, setRunning] = useState(false);
  const existing = project.audio.files;

  function add(files: File[]) {
    const merged = [...items.filter((item) => item.status !== "done").map((item) => item.file), ...files];
    const unique = Array.from(new Map(merged.map((file) => [file.name, file])).values());
    unique.sort((a, b) => naturalCompare(a.name, b.name));
    setItems(unique.map((file) => ({ file, progress: 0, status: "waiting" })));
  }

  function patchItem(index: number, change: Partial<UploadItem>) {
    setItems((current) => current.map((item, at) => (at === index ? { ...item, ...change } : item)));
  }

  async function start() {
    const queue = items.map((item, index) => ({ item, index })).filter(({ item }) => item.status !== "done");
    if (!queue.length) return;
    setRunning(true);
    const quiet = queue.length > 1;
    let latest = null as Project | null;
    let failed = 0;
    // One at a time: narration files are large, and order is what the user checks.
    await pool(queue, 1, async ({ item, index }) => {
      patchItem(index, { status: "uploading", progress: 0, message: undefined });
      try {
        const result = await upload<Partial<ProjectEnvelope>>(projectPath(project.id, "audio", item.file.name), item.file, {
          query: { replace: replace ? 1 : undefined, quiet: quiet ? 1 : undefined },
          onProgress: (progress) => patchItem(index, { progress }),
        });
        if (result.project) latest = result.project;
        patchItem(index, { status: "done", progress: 1 });
      } catch (error) {
        failed += 1;
        const apiError = toApiError(error);
        patchItem(index, {
          status: apiError.code === "exists" ? "exists" : "failed",
          message:
            apiError.code === "exists"
              ? "A narration file with this name is already here. Tick Replace files with the same name to overwrite it."
              : apiError.message,
        });
      }
    });
    if (latest) onProject(latest);
    else await refetch();
    setRunning(false);
    if (!failed) {
      toast({
        tone: "done",
        message: queue.length === 1 ? `Uploaded ${queue[0].item.file.name}` : `Uploaded ${queue.length} narration files`,
        detail: project.transcript ? "The transcript was made from the old narration. Transcribe again to match." : undefined,
      });
      onClose();
    }
  }

  const pending = items.filter((item) => item.status !== "done").length;

  return (
    <Dialog
      title="Upload narration"
      size="lg"
      onClose={onClose}
      dismissible={!running}
      description="Drop or choose audio files. Several files are joined into one narration, in name order."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={running}>
            {items.some((item) => item.status === "done") ? "Close" : "Cancel"}
          </Button>
          <Button variant="primary" onClick={() => void start()} disabled={running || locked || pending === 0}>
            {running ? "Uploading" : pending > 1 ? `Upload ${pending} files` : "Upload"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {locked ? <Banner tone="info" title="The narration is locked">{lockedReason}</Banner> : null}

        {existing.length ? (
          <div className="flex flex-col gap-1.5">
            <p className="text-sm font-medium">
              In this project now{project.audio.seconds ? <span className="timecode font-normal text-muted">, {clock(project.audio.seconds)} in all</span> : null}
            </p>
            <ol className="divide-y divide-hairline rounded-[var(--radius-control)] border border-hairline">
              {existing.map((file, index) => (
                <li key={file.name} className="flex items-center gap-3 px-3 py-1.5 text-sm">
                  <span className="timecode w-6 text-muted">{index + 1}</span>
                  <span className="min-w-0 flex-1 truncate">{file.name}</span>
                  <span className="timecode text-xs text-muted">{clock(file.seconds)}</span>
                  <span className="timecode w-16 text-right text-xs text-muted">{bytes(file.bytes)}</span>
                  <IconButton label={`Remove ${file.name}`} disabled={locked || running} onClick={() => void onRemove(file.name)}>
                    <Trash2 size={15} aria-hidden />
                  </IconButton>
                </li>
              ))}
            </ol>
          </div>
        ) : null}

        <DropZone
          accept={ACCEPT}
          multiple
          disabled={locked || running}
          onFiles={add}
          title={existing.length ? "Drop more audio, or choose files" : "Drop the narration here, or choose files"}
          hint="WAV, MP3, M4A, FLAC or OGG, up to 2 GB each."
        />

        {items.length ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted">{items.length > 1 ? "Joined in this order, by name:" : "Ready to upload:"}</p>
            <UploadList items={items} numbered={items.length > 1} />
            <Checkbox
              checked={replace}
              onChange={setReplace}
              disabled={running}
              label="Replace files with the same name"
              hint="The file it replaces goes to the trash and can be restored for 7 days."
            />
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}
