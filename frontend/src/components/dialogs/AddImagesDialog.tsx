"use client";

import { useMemo, useState } from "react";
import { pool, projectPath, toApiError, upload } from "@/lib/api";
import { leadingNumber, naturalCompare, plural } from "@/lib/format";
import type { Project } from "@/lib/types";
import { Banner } from "../studio/Banners";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { useToast } from "../ui/Toast";
import { DropZone, UploadList, type UploadItem } from "./DropZone";

type Props = {
  project: Project;
  locked: boolean;
  lockedReason: string | null;
  initialFiles?: File[];
  onClose: () => void;
  refetch: () => Promise<void>;
};

const ACCEPT = "image/*,.jpg,.jpeg,.png,.webp,.bmp,.gif,.tif,.tiff";

function sorted(files: File[]): File[] {
  const unique = Array.from(new Map(files.map((file) => [file.name, file])).values());
  return unique.sort((a, b) => naturalCompare(a.name, b.name));
}

/**
 * Many images at once. Each goes on the line its filename number names, so
 * 012 goes on line 12. Three upload at a time, then the project is read once.
 */
export function AddImagesDialog({ project, locked, lockedReason, initialFiles, onClose, refetch }: Props) {
  const { toast } = useToast();
  const [items, setItems] = useState<UploadItem[]>(() =>
    sorted(initialFiles ?? []).map((file) => ({ file, progress: 0, status: "waiting" })),
  );
  const [running, setRunning] = useState(false);

  const lines = project.storyboard.length;
  const base = project.images.base;

  const analysis = useMemo(() => {
    const names = new Set<string>([
      ...project.storyboard.flatMap((line) => (line.image ? [line.image.name] : [])),
      ...project.images.unplaced.map((image) => image.name),
    ]);
    let noNumber = 0;
    let pastEnd = 0;
    let occupied = 0;
    let lowest = Infinity;
    let highest = -Infinity;
    for (const item of items) {
      if (item.status === "done") continue;
      const number = leadingNumber(item.file.name);
      if (number === null) {
        noNumber += 1;
        continue;
      }
      const line = number - base + 1;
      if (lines && line > lines) {
        pastEnd += 1;
        continue;
      }
      lowest = Math.min(lowest, line);
      highest = Math.max(highest, line);
      const slot = project.storyboard[line - 1];
      if (slot?.image && slot.image.name !== item.file.name && !names.has(item.file.name)) occupied += 1;
    }
    return { noNumber, pastEnd, occupied, lowest, highest };
  }, [items, project.storyboard, project.images.unplaced, base, lines]);

  function add(files: File[]) {
    const kept = items.filter((item) => item.status !== "done").map((item) => item.file);
    setItems(sorted([...kept, ...files]).map((file) => ({ file, progress: 0, status: "waiting" })));
  }

  function patchItem(index: number, change: Partial<UploadItem>) {
    setItems((current) => current.map((item, at) => (at === index ? { ...item, ...change } : item)));
  }

  async function start(replace: boolean) {
    const queue = items
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => (replace ? item.status === "exists" : item.status === "waiting" || item.status === "failed"));
    if (!queue.length) return;
    setRunning(true);
    let failed = 0;
    let clashes = 0;
    await pool(queue, 3, async ({ item, index }) => {
      patchItem(index, { status: "uploading", progress: 0, message: undefined });
      try {
        await upload(projectPath(project.id, "images", item.file.name), item.file, {
          query: { quiet: 1, replace: replace ? 1 : undefined },
          onProgress: (progress) => patchItem(index, { progress }),
        });
        patchItem(index, { status: "done", progress: 1 });
      } catch (error) {
        const apiError = toApiError(error);
        if (apiError.code === "exists") {
          clashes += 1;
          patchItem(index, { status: "exists", message: "An image with this name is already in the project." });
        } else {
          failed += 1;
          patchItem(index, { status: "failed", message: apiError.message });
        }
      }
    });
    await refetch();
    setRunning(false);
    const done = queue.length - failed - clashes;
    if (!failed && !clashes) {
      toast({ tone: "done", message: `Added ${plural(done, "image")}` });
      onClose();
    } else if (done) {
      toast({ tone: "info", message: `Added ${plural(done, "image")}`, detail: "Some were not. The dialog says why." });
    }
  }

  const waiting = items.filter((item) => item.status === "waiting" || item.status === "failed").length;
  const conflicts = items.filter((item) => item.status === "exists").length;
  const positional = project.images.mode === "positional";

  return (
    <Dialog
      title="Add images"
      size="lg"
      onClose={onClose}
      dismissible={!running}
      description="Each image goes on the line its filename number names: 012.jpg goes on line 12, and so does 012. two men talking.jpg."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={running}>
            {items.some((item) => item.status === "done") ? "Close" : "Cancel"}
          </Button>
          {conflicts ? (
            <Button variant="secondary" onClick={() => void start(true)} disabled={running || locked}>
              Replace {plural(conflicts, "image")} with the same name
            </Button>
          ) : null}
          <Button variant="primary" onClick={() => void start(false)} disabled={running || locked || waiting === 0}>
            {running ? "Uploading" : waiting ? `Upload ${plural(waiting, "image")}` : "Upload"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {locked ? <Banner tone="info" title="Images are locked">{lockedReason}</Banner> : null}
        <DropZone
          accept={ACCEPT}
          multiple
          disabled={locked || running}
          onFiles={add}
          title="Drop images here, or choose them"
          hint="JPG, PNG or WebP, up to 50 MB each. To put one image on one line, drop it on that line in the storyboard instead."
        />

        {items.length && !lines ? (
          <Banner tone="info" title="There is no transcript yet">
            The images wait in Unplaced until there is one, then each goes on the line its number names.
          </Banner>
        ) : null}
        {analysis.noNumber && lines && !positional ? (
          <Banner tone="attention" title={`${plural(analysis.noNumber, "name")} ${analysis.noNumber === 1 ? "does" : "do"} not start with a number`}>
            Then the whole folder is paired with lines in name order instead of by number, and one missing
            image would shift every image after it. Rename them first, or use Renumber afterwards.
          </Banner>
        ) : null}
        {positional && items.length ? (
          <Banner tone="attention" title="This folder is paired by position">
            New images join in name order, not by number. Renumber images to fix each one to its line.
          </Banner>
        ) : null}
        {analysis.occupied ? (
          <Banner tone="attention" title={`${plural(analysis.occupied, "image")} would share a line with an image already there`}>
            Two images on one line stop the video from building. To replace an image, drop the new file on
            its line in the storyboard instead.
          </Banner>
        ) : null}
        {analysis.pastEnd ? (
          <Banner tone="info" title={`${plural(analysis.pastEnd, "number")} past the last line, ${lines}`}>
            Those images wait in Unplaced until you drag them onto a line.
          </Banner>
        ) : null}

        {items.length ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted">
              {plural(items.length, "image")}
              {Number.isFinite(analysis.lowest)
                ? analysis.lowest === analysis.highest
                  ? `, for line ${analysis.lowest}`
                  : `, for lines ${analysis.lowest} to ${analysis.highest}`
                : ""}
            </p>
            <UploadList items={items} />
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}
