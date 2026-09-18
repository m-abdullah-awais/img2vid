"use client";

import { useState } from "react";
import { post, projectPath, toApiError } from "@/lib/api";
import { useSystem } from "@/lib/hooks/useSystem";
import type { Job, ModelName, Project, TranscribeBody } from "@/lib/types";
import { Banner } from "../studio/Banners";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Checkbox, Choice, Field, TextInput } from "../ui/Field";

type Props = {
  project: Project;
  busy: string | null;
  locked: boolean;
  lockedReason: string | null;
  onClose: () => void;
  onStarted: (job: Job) => void;
};

const MODEL_NOTES: Record<ModelName, string> = {
  tiny: "Fastest and roughest. Expect about twice the mistakes of base.",
  base: "Accurate on clear narration, and several times faster than it plays.",
  small: "Much slower, and on this computer no more accurate than base.",
};

type Length = "0" | "60" | "90" | "120";

/** Turn the narration into timed lines, on this computer. */
export function TranscribeDialog({ project, busy, locked, lockedReason, onClose, onStarted }: Props) {
  // The system report says which models are already here. Skipped while a job runs.
  const { system } = useSystem(!busy);
  const [model, setModel] = useState<ModelName>("base");
  const [language, setLanguage] = useState("");
  const [length, setLength] = useState<Length>("0");
  const [fresh, setFresh] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const local = new Map(system?.speech.models.map((entry) => [entry.name, entry.local]) ?? []);
  const hasTranscript = Boolean(project.transcript);

  async function start() {
    setStarting(true);
    setError(null);
    const body: TranscribeBody = {
      model,
      language: language.trim() || null,
      maxChars: Number(length),
      fresh,
    };
    try {
      const { job } = await post<{ job: Job }>(projectPath(project.id, "transcribe"), body);
      onStarted(job);
      onClose();
    } catch (failure) {
      setError(toApiError(failure).message);
      setStarting(false);
    }
  }

  const note = (name: ModelName) => {
    const here = local.get(name);
    if (here === undefined) return MODEL_NOTES[name];
    return `${MODEL_NOTES[name]} ${here ? "Already on this computer." : "Downloads once, before the first use."}`;
  };

  return (
    <Dialog
      title="Transcribe narration"
      size="md"
      onClose={onClose}
      dismissible={!starting}
      description="Runs on this computer. Nothing is uploaded anywhere."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={starting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => void start()}
            disabled={starting || Boolean(busy) || locked}
            title={busy ?? lockedReason ?? undefined}
          >
            {starting ? "Starting" : "Transcribe"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {busy ? <Banner tone="info" title="The engine is busy">{busy}</Banner> : null}
        {locked && !busy ? <Banner tone="info" title="The transcript is locked">{lockedReason}</Banner> : null}

        <Choice<ModelName>
          legend="Model"
          layout="stacked"
          value={model}
          onChange={setModel}
          options={(["tiny", "base", "small"] as ModelName[]).map((name) => ({
            value: name,
            label: name === "base" ? "base, recommended" : name,
            note: note(name),
          }))}
        />

        <Field
          label="Language"
          hint="Leave it empty to detect the language. Otherwise a code such as en, de, fr or ur."
        >
          {({ id, describedBy }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              value={language}
              maxLength={8}
              autoComplete="off"
              spellCheck={false}
              placeholder="auto"
              className="max-w-[10rem]"
              onChange={(event) => setLanguage(event.target.value)}
            />
          )}
        </Field>

        <Choice<Length>
          legend="Line length"
          value={length}
          onChange={setLength}
          hint="The most characters on one line. Each line gets one image, so this sets how many images the video needs: shorter lines, more images."
          options={[
            { value: "0", label: "Off" },
            { value: "60", label: <span className="timecode">60</span> },
            { value: "90", label: <span className="timecode">90</span> },
            { value: "120", label: <span className="timecode">120</span> },
          ]}
        />

        <Checkbox
          checked={fresh}
          onChange={setFresh}
          label="Transcribe again even if done before"
          hint="Without this, the same narration with the same settings reuses the earlier result in a second."
        />

        {hasTranscript ? (
          <Banner tone="attention" title={`This replaces the current transcript, ${project.transcript?.lines ?? 0} lines`}>
            The old one goes to the trash and can be restored for 7 days. Images stay on their numbers,
            so if the line count changes, check the storyboard afterwards.
          </Banner>
        ) : null}

        {error ? <Banner tone="error" title="Transcription did not start">{error}</Banner> : null}
      </div>
    </Dialog>
  );
}
