"use client";

import { useState } from "react";
import { plural } from "@/lib/format";
import type { ArrangePreview } from "@/lib/types";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";

type Props = {
  preview: ArrangePreview;
  onConfirm: () => Promise<void>;
  onClose: () => void;
};

/**
 * A folder paired by position has no numbers to move. The first arrangement
 * numbers every image in the order it is shown now, which is a real change,
 * so it is asked about once.
 */
export function ArrangeConfirmDialog({ preview, onConfirm, onClose }: Props) {
  const [working, setWorking] = useState(false);
  const renamed = preview.changes.filter((change) => change.from !== change.to).length;
  return (
    <Dialog
      title="Number the images first?"
      size="md"
      onClose={onClose}
      dismissible={!working}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={working}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={working}
            onClick={async () => {
              setWorking(true);
              await onConfirm();
              onClose();
            }}
          >
            {working ? "Numbering" : "Number them and move"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-base">
          These images are paired with lines by position, so none of them has a number to move yet.
        </p>
        <p className="text-muted">
          Moving one first numbers every image in the order the storyboard shows now
          {renamed ? `, which renames ${plural(renamed, "file")}` : ""}. From then on each image stays on its
          line, and a missing one no longer shifts the rest. Undo reverses both.
        </p>
        {preview.summary ? (
          <p className="rounded-[var(--radius-control)] border border-hairline px-3 py-2">{preview.summary}</p>
        ) : null}
      </div>
    </Dialog>
  );
}
