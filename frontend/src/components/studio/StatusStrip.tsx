"use client";

import { memo, type ComponentProps, type ReactNode } from "react";
import { stepDot, stepText } from "@/lib/tone";
import type { Project, Step } from "@/lib/types";
import { Button, type ButtonVariant } from "../ui/Button";

export type StripActions = {
  onNarration: () => void;
  onTranscribe: () => void;
  onUploadTranscript: () => void;
  onEditTranscript: () => void;
  onDownloadTranscript: () => void;
  onAddImages: () => void;
  onBuild: () => void;
};

type Props = StripActions & {
  project: Project;
  locked: { audio: boolean; transcript: boolean; images: boolean };
  busy: string | null;
  lockedReason: string | null;
};

const stateWords: Record<Step["state"], string> = {
  missing: "not done yet",
  ready: "done",
  attention: "needs attention",
  busy: "in progress",
};

function StepCell({
  number,
  title,
  step,
  children,
}: {
  number: number;
  title: string;
  step: Step;
  children: ReactNode;
}) {
  return (
    <li className="grid grid-cols-[1.125rem_minmax(0,1fr)] grid-rows-[auto_1fr_auto] gap-x-1.5 gap-y-1 px-3.5 py-3">
      <span className="timecode text-base leading-6 text-muted">{number}</span>
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">{title}</h3>
        <span
          aria-hidden
          className={`ml-auto h-2 w-2 shrink-0 rounded-full ${stepDot[step.state]}`}
          title={stateWords[step.state]}
        />
        <span className="sr-only">, {stateWords[step.state]}</span>
      </div>
      <div className="col-start-2 text-sm">
        <p className={`break-words ${step.state === "missing" ? "text-muted" : "text-text"}`}>{step.summary}</p>
        {step.detail ? <p className={`break-words ${stepText[step.state]}`}>{step.detail}</p> : null}
      </div>
      <div className="col-start-2 -ml-[5px] flex flex-wrap pt-2">{children}</div>
    </li>
  );
}

function StepButton({
  variant = "ghost",
  className = "",
  ...rest
}: ComponentProps<typeof Button> & { variant?: ButtonVariant }) {
  // A ghost button's label lines up with the summary above; a filled one lines up by its edge.
  const tight = variant === "ghost" ? "px-[5px]" : "ml-[5px] mr-1";
  return <Button size="sm" variant={variant} className={`${tight} ${className}`} {...rest} />;
}

/**
 * The four steps as one segmented strip. They are a real sequence, which is
 * what earns them their numbers. The next step to take is the one filled button.
 */
export const StatusStrip = memo(function StatusStrip({
  project,
  locked,
  busy,
  lockedReason,
  onNarration,
  onTranscribe,
  onUploadTranscript,
  onEditTranscript,
  onDownloadTranscript,
  onAddImages,
  onBuild,
}: Props) {
  const { steps } = project;
  const hasAudio = project.audio.files.length > 0;
  const hasTranscript = Boolean(project.transcript);
  const why = (isLocked: boolean) => (isLocked ? lockedReason ?? undefined : undefined);

  return (
    <ol
      aria-label="Steps"
      className="grid divide-y divide-hairline rounded-[var(--radius-control)] border border-hairline bg-panel lg:grid-cols-4 lg:divide-x lg:divide-y-0"
    >
      <StepCell number={1} title="Narration" step={steps.narration}>
        <StepButton
          variant={hasAudio ? "ghost" : "primary"}
          onClick={onNarration}
          disabled={locked.audio}
          title={why(locked.audio)}
          aria-label={hasAudio ? "Change narration" : "Upload narration"}
        >
          {hasAudio ? "Change" : "Upload"}
        </StepButton>
      </StepCell>

      <StepCell number={2} title="Transcript" step={steps.transcript}>
        <StepButton
          variant={hasAudio && !hasTranscript ? "primary" : "ghost"}
          onClick={onTranscribe}
          disabled={locked.transcript || !hasAudio || Boolean(busy)}
          title={busy ?? why(locked.transcript) ?? (!hasAudio ? "Upload the narration first" : undefined)}
        >
          Transcribe
        </StepButton>
        <StepButton
          onClick={onUploadTranscript}
          disabled={locked.transcript}
          title={why(locked.transcript)}
          aria-label="Upload transcript"
        >
          Upload
        </StepButton>
        {hasTranscript ? (
          <>
            <StepButton
              onClick={onEditTranscript}
              disabled={locked.transcript}
              title={why(locked.transcript)}
              aria-label="Edit transcript"
            >
              Edit
            </StepButton>
            <StepButton onClick={onDownloadTranscript} aria-label="Download transcript">
              Download
            </StepButton>
          </>
        ) : null}
      </StepCell>

      <StepCell number={3} title="Images" step={steps.images}>
        <StepButton
          variant={hasTranscript && project.images.total === 0 ? "primary" : "ghost"}
          onClick={onAddImages}
          disabled={locked.images}
          title={why(locked.images)}
        >
          Add images
        </StepButton>
      </StepCell>

      <StepCell number={4} title="Video" step={steps.video}>
        <StepButton onClick={onBuild} disabled={Boolean(busy)} title={busy ?? undefined}>
          Build video
        </StepButton>
      </StepCell>
    </ol>
  );
});
