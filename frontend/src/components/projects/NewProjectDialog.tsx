"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { post, toApiError } from "@/lib/api";
import type { ProjectEnvelope } from "@/lib/types";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Field, TextInput } from "../ui/Field";

/** Name it, create it, and go straight to it to upload the narration. */
export function NewProjectDialog({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function create() {
    const clean = name.trim();
    if (!clean) {
      setError("Give the project a name, for example the video's title.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const { project } = await post<ProjectEnvelope>("/api/projects", { name: clean });
      router.push(`/projects/${project.id}`);
    } catch (failure) {
      setError(toApiError(failure).message);
      setSaving(false);
    }
  }

  return (
    <Dialog
      title="New project"
      size="sm"
      onClose={onClose}
      dismissible={!saving}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="new-project" disabled={saving}>
            {saving ? "Creating project" : "Create project"}
          </Button>
        </>
      }
    >
      <form
        id="new-project"
        onSubmit={(event) => {
          event.preventDefault();
          void create();
        }}
      >
        <Field
          label="Name"
          hint="Usually the video's title. You can rename it later."
          error={error}
        >
          {({ id, describedBy }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              aria-invalid={Boolean(error)}
              value={name}
              maxLength={120}
              data-autofocus
              autoComplete="off"
              placeholder="Florian"
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
      </form>
    </Dialog>
  );
}
