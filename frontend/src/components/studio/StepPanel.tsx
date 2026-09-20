"use client";

import { Download, ImagePlus, Play } from "lucide-react";
import { memo, type ReactNode } from "react";
import { apiUrl, projectPath } from "@/lib/api";
import { bytes, clock, plural, stamp } from "@/lib/format";
import { STEP_TITLES, type Stage, type StepNumber } from "@/lib/stage";
import type { Project } from "@/lib/types";
import { DropZone } from "../dialogs/DropZone";
import { Button, buttonClass } from "../ui/Button";
import { StepBanners } from "./Banners";

export type StepActions = {
  onNarration: () => void;
  onTranscribe: () => void;
  onUploadTranscript: () => void;
  onEditTranscript: () => void;
  onDownloadTranscript: () => void;
  onAddImages: () => void;
  onRenumber: () => void;
  onBuild: () => void;
};

type Props = {
  project: Project;
  stage: Stage;
  /** The step on screen, which is the current one unless a done marker was pressed. */
  shown: StepNumber;
  locked: { audio: boolean; transcript: boolean; images: boolean };
  lockedReason: string | null;
  busy: string | null;
  /** A job for this project, so the step it belongs to can say so. */
  transcribing: boolean;
  rendering: boolean;
  actions: StepActions;
  onBack: () => void;
  onNarrationFiles: (files: File[]) => void;
  onPlay: (name: string) => void;
};

const AUDIO = "audio/*,.wav,.mp3,.m4a,.aac,.flac,.ogg,.opus,.wma";

type Body = { title: string; message: string; children?: ReactNode; actions: ReactNode };

/**
 * One panel, for one step: where you are, what to do now, why it matters, and
 * the way to do it. Nothing a step cannot use is on the page at all, so there
 * is never a control here that does nothing yet.
 */
export const StepPanel = memo(function StepPanel({
  project,
  stage,
  shown,
  locked,
  lockedReason,
  busy,
  transcribing,
  rendering,
  actions,
  onBack,
  onNarrationFiles,
  onPlay,
}: Props) {
  const revisiting = shown !== stage.step;
  const why = (isLocked: boolean) => busy ?? (isLocked ? (lockedReason ?? undefined) : undefined);
  const body = build();

  function narration(): Body {
    const files = project.audio.files;
    const length = project.audio.seconds !== null ? clock(project.audio.seconds) : null;
    const named = files.length === 1 ? files[0].name : `${files.length} audio files`;
    const change = (
      <Button
        variant={revisiting ? "secondary" : "primary"}
        onClick={actions.onNarration}
        disabled={locked.audio}
        title={why(locked.audio)}
      >
        {files.length ? "Change narration" : "Upload narration"}
      </Button>
    );
    if (revisiting) {
      return {
        title: "Your narration.",
        message: `${named}${length ? `, ${length}` : ""}. It sets the timing of everything: the transcript is made from it, and the video is exactly as long as it is. Replacing it leaves the transcript out of date, so transcribe again afterwards.`,
        actions: change,
      };
    }
    return {
      title: stage.title,
      message: stage.message,
      children: (
        <DropZone
          accept={AUDIO}
          multiple
          disabled={locked.audio}
          onFiles={onNarrationFiles}
          title="Drop the narration here, or choose files"
          hint="WAV, MP3, M4A, FLAC or OGG, up to 2 GB each."
        />
      ),
      actions: change,
    };
  }

  function transcript(): Body {
    const lines = project.storyboard.length;
    const file = project.transcript;
    // Plain text when the lines can be read, and the file exactly as it is
    // when they cannot, since converting it is what failed.
    const download = file ? (
      <a
        className={buttonClass(revisiting ? "secondary" : "ghost", "md")}
        href={apiUrl(`${projectPath(project.id, "transcript", "download")}${lines ? "?format=txt" : ""}`)}
      >
        <Download size={15} aria-hidden />
        Download transcript
      </a>
    ) : null;

    if (transcribing) {
      return {
        title: "Turning your narration into lines.",
        message:
          "img2vid is listening to the narration on this computer. Its progress is in the bar at the bottom of the window, and the lines appear here when it finishes.",
        actions: (
          <Button variant="primary" disabled title={lockedReason ?? undefined}>
            Transcribing narration
          </Button>
        ),
      };
    }

    const transcribe = (
      <Button
        variant={revisiting ? "secondary" : "primary"}
        onClick={actions.onTranscribe}
        disabled={locked.transcript || Boolean(busy)}
        title={why(locked.transcript)}
      >
        {file ? "Transcribe again" : "Transcribe narration"}
      </Button>
    );
    const upload = (
      <Button
        variant={revisiting ? "secondary" : "ghost"}
        onClick={actions.onUploadTranscript}
        disabled={locked.transcript}
        title={why(locked.transcript)}
      >
        Upload transcript
      </Button>
    );

    if (revisiting) {
      return {
        title: "Your transcript.",
        message: `${file ? file.name : "The transcript"}, ${plural(lines, "line")}. Each line puts one image on screen and holds it until the next line starts, so the lines are the video's timing. An image keeps the line number in its filename, so editing the words here does not move it.`,
        actions: (
          <>
            {transcribe}
            {upload}
            <Button
              variant="secondary"
              onClick={actions.onEditTranscript}
              disabled={locked.transcript}
              title={why(locked.transcript)}
            >
              Edit transcript
            </Button>
            {download}
            <Button variant="quiet" onClick={actions.onDownloadTranscript}>
              Other formats
            </Button>
          </>
        ),
      };
    }
    return {
      title: stage.title,
      message: stage.message,
      actions: (
        <>
          {transcribe}
          {upload}
          {download}
        </>
      ),
    };
  }

  function images(): Body {
    const add = (
      <Button
        variant={revisiting ? "secondary" : "primary"}
        onClick={actions.onAddImages}
        disabled={locked.images}
        title={why(locked.images)}
      >
        <ImagePlus size={15} aria-hidden />
        Add images
      </Button>
    );
    if (revisiting) {
      return {
        title: "Your images.",
        message: `${plural(project.images.total, "image")}, one on every one of the ${project.storyboard.length} lines. An image whose filename starts with the line number stays on that line, and you can move any of them in the timeline or the storyboard below.`,
        actions: add,
      };
    }
    return {
      title: stage.title,
      message: stage.message,
      actions: (
        <>
          {add}
          {project.images.missing.length ? (
            <Button variant="quiet" onClick={actions.onBuild} disabled={Boolean(busy)} title={busy ?? undefined}>
              Build with the empty lines as black screens
            </Button>
          ) : null}
        </>
      ),
    };
  }

  function video(): Body {
    if (rendering) {
      return {
        title: "Building your video.",
        message:
          "img2vid is writing the MP4 on this computer. Its progress is in the bar at the bottom of the window, and the finished video appears here.",
        actions: (
          <Button variant="primary" disabled>
            Building video
          </Button>
        ),
      };
    }
    const newest = project.videos[0];
    if (!newest) {
      return {
        title: stage.title,
        message: stage.message,
        actions: (
          <Button variant="primary" onClick={actions.onBuild} disabled={Boolean(busy)} title={busy ?? undefined}>
            Build video
          </Button>
        ),
      };
    }
    return {
      title: stage.title,
      message: stage.message,
      children: (
        <p className="timecode flex flex-wrap gap-x-5 text-sm text-muted">
          <span className="text-text">{newest.name}</span>
          <span>{clock(newest.seconds)}</span>
          <span>{bytes(newest.bytes)}</span>
          <span>Built {stamp(newest.createdAt)}</span>
        </p>
      ),
      actions: (
        <>
          <Button variant="primary" onClick={() => onPlay(newest.name)}>
            <Play size={15} aria-hidden />
            Play
          </Button>
          <a className={buttonClass("secondary", "md")} href={apiUrl(newest.download)}>
            <Download size={15} aria-hidden />
            Download
          </a>
          <Button variant="secondary" onClick={actions.onBuild} disabled={Boolean(busy)} title={busy ?? undefined}>
            Build again
          </Button>
        </>
      ),
    };
  }

  function build(): Body {
    if (shown === 1) return narration();
    if (shown === 2) return transcript();
    if (shown === 3) return images();
    return video();
  }

  return (
    <section
      aria-labelledby="step-title"
      className="max-w-[880px] rounded-[var(--radius-control)] border border-hairline bg-panel px-5 py-5 sm:px-6 sm:py-6"
    >
      <div className="flex flex-col gap-3">
        {/* Prose keeps a readable measure; the controls use the panel. */}
        <div className="flex max-w-[68ch] flex-col gap-1.5" aria-live="polite">
          <p className="timecode text-sm text-muted">Step {shown} of 4</p>
          <h2 id="step-title" className="heading text-2xl">
            {body.title}
          </h2>
          <p className="text-muted">{body.message}</p>
        </div>

        {/* The step the job belongs to says so itself; every other step only
            needs to know why its controls are off. */}
        {lockedReason && !(shown === 2 && transcribing) && !(shown === 4 && rendering) ? (
          <p role="status" className="max-w-[68ch] text-sm text-muted">
            {lockedReason}
          </p>
        ) : null}

        <StepBanners
          project={project}
          step={shown}
          busy={busy}
          onRenumber={actions.onRenumber}
          onTranscribe={actions.onTranscribe}
        />

        {body.children}

        <div className="flex flex-wrap items-center gap-2 pt-1">{body.actions}</div>

        {/* A finished step is a detour. The way on stays in sight. */}
        {revisiting ? (
          <p className="text-sm">
            <button
              type="button"
              onClick={onBack}
              className="rounded-[var(--radius-control)] text-muted underline decoration-hairline underline-offset-4 hover:text-text hover:decoration-text"
            >
              Back to step {stage.step}, {STEP_TITLES[stage.step].toLowerCase()}
            </button>
          </p>
        ) : null}
      </div>
    </section>
  );
});
