"use client";

import { ChevronLeft, Pencil } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { patch, projectPath, toApiError, type ApiError } from "@/lib/api";
import type { DragSource, DropTarget } from "@/lib/arrange";
import { useProject } from "@/lib/hooks/useProject";
import type { ArrangeBody, ArrangePreview, Job, Project, ProjectEnvelope } from "@/lib/types";
import { AddImagesDialog } from "../dialogs/AddImagesDialog";
import { ArrangeConfirmDialog } from "../dialogs/ArrangeConfirmDialog";
import { BuildDialog } from "../dialogs/BuildDialog";
import { ImageDialog } from "../dialogs/ImageDialog";
import { RenumberDialog } from "../dialogs/RenumberDialog";
import { TranscribeDialog } from "../dialogs/TranscribeDialog";
import { DownloadTranscriptDialog, EditTranscriptDialog, UploadTranscriptDialog } from "../dialogs/TranscriptDialogs";
import { UploadNarrationDialog } from "../dialogs/UploadNarrationDialog";
import { busyReason, useEngineOnline, useJob, useJobActions, useJobFinished, useRunning } from "../job/JobProvider";
import { Button, IconButton } from "../ui/Button";
import { EngineDown } from "../ui/EngineDown";
import { useToast } from "../ui/Toast";
import { ArrangeDnd } from "./ArrangeDnd";
import { Banners } from "./Banners";
import { CoverageTimeline } from "./CoverageTimeline";
import { StatusStrip } from "./StatusStrip";
import { Storyboard, type Filter, type View } from "./Storyboard";
import { useStudioActions } from "./useStudioActions";
import { VideosPanel } from "./VideosPanel";

type DialogState =
  | { kind: "narration" }
  | { kind: "transcribe" }
  | { kind: "upload-transcript" }
  | { kind: "edit-transcript" }
  | { kind: "download-transcript" }
  | { kind: "images"; files?: File[] }
  | { kind: "image"; line: number }
  | { kind: "renumber" }
  | { kind: "build" }
  | { kind: "arrange"; body: ArrangeBody; preview: ArrangePreview }
  | null;

export function Studio({ id }: { id: string }) {
  const { project, error, refetch, setProject } = useProject(id);
  const engineDown = useJob((state) => state.offline === true);
  const { refresh } = useJobActions();

  useJobFinished((job) => {
    if (job.projectId === id) void refetch();
  });
  useEngineOnline(() => void refetch());

  const name = project?.name;
  useEffect(() => {
    if (name) document.title = `${name} | img2vid`;
  }, [name]);

  const retry = useCallback(async () => {
    refresh();
    await refetch();
  }, [refresh, refetch]);

  if (engineDown || (error?.code === "unreachable" && !project)) return <EngineDown onRetry={retry} />;
  if (!project) {
    if (error?.code === "not_found") return <ProjectGone />;
    if (error) return <LoadFailed error={error} onRetry={retry} />;
    return (
      <p className="py-10 text-sm text-muted" aria-live="polite">
        Loading project
      </p>
    );
  }
  return <StudioView project={project} setProject={setProject} refetch={refetch} />;
}

function ProjectGone() {
  return (
    <section className="flex flex-col items-start gap-4 py-16">
      <h1 className="heading text-3xl">This project is not here</h1>
      <p className="max-w-[60ch] text-muted">
        It may have been deleted. A deleted project stays in the trash for 7 days, and Undo on the
        projects page brings it back while its message is showing.
      </p>
      <Link href="/" className="text-sm font-semibold underline decoration-hairline underline-offset-4 hover:decoration-text">
        Back to projects
      </Link>
    </section>
  );
}

function LoadFailed({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <section className="flex flex-col items-start gap-4 py-16">
      <h1 className="heading text-3xl">The project could not be opened</h1>
      <p className="max-w-[60ch] text-muted">{error.message}</p>
      <Button variant="primary" onClick={onRetry}>
        Retry
      </Button>
    </section>
  );
}

function ProjectTitle({ project, onProject }: { project: Project; onProject: (project: Project) => void }) {
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(project.name);

  async function save() {
    const clean = draft.trim();
    setEditing(false);
    if (!clean || clean === project.name) return;
    try {
      const result = await patch<ProjectEnvelope>(projectPath(project.id), { name: clean });
      onProject(result.project);
    } catch (failure) {
      toast({ tone: "error", message: "Not renamed", detail: toApiError(failure).message });
    }
  }

  if (editing) {
    return (
      <form
        className="min-w-0 flex-1"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label htmlFor="project-name" className="sr-only">
          Project name
        </label>
        <input
          id="project-name"
          value={draft}
          autoFocus
          maxLength={120}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => void save()}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              setEditing(false);
            }
          }}
          className="heading h-11 w-full max-w-[640px] rounded-[var(--radius-control)] border border-text bg-graphite px-2 text-3xl"
        />
      </form>
    );
  }
  return (
    <div className="flex min-w-0 items-center gap-2">
      <h1 className="heading text-3xl break-words">{project.name}</h1>
      <IconButton
        label="Rename project"
        onClick={() => {
          setDraft(project.name);
          setEditing(true);
        }}
      >
        <Pencil size={16} aria-hidden />
      </IconButton>
    </div>
  );
}

type ViewProps = {
  project: Project;
  setProject: (project: Project) => void;
  refetch: () => Promise<void>;
};

function StudioView({ project, setProject, refetch }: ViewProps) {
  const running = useRunning();
  const jobs = useJobActions();
  const { toast } = useToast();

  const [dialog, setDialog] = useState<DialogState>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [view, setView] = useState<View>("list");
  const [uploads, setUploads] = useState<Record<number, number>>({});
  const [focus, setFocus] = useState<{ line: number; nonce: number } | null>(null);

  const latest = useRef(project);
  const filterRef = useRef(filter);
  useEffect(() => {
    latest.current = project;
    filterRef.current = filter;
  });

  const busy = busyReason(running);
  const mine = running.projectId === project.id;
  const renderingHere = mine && running.kind === "render";
  const transcribingHere = mine && running.kind === "transcribe";

  const lockAudio = project.locked.audio || renderingHere || transcribingHere;
  const lockTranscript = project.locked.transcript || renderingHere || transcribingHere;
  const lockImages = project.locked.images || renderingHere;
  const locked = useMemo(
    () => ({ audio: lockAudio, transcript: lockTranscript, images: lockImages }),
    [lockAudio, lockTranscript, lockImages],
  );
  const lockedReason =
    lockAudio || lockTranscript || lockImages
      ? transcribingHere
        ? "The narration is being transcribed. The narration and transcript can change again once it finishes. Images can be arranged meanwhile."
        : renderingHere
          ? "A video is being built from this project. Its narration, transcript and images can change again once it finishes."
          : "The engine is using this project's files for a job. They can change again once it finishes."
      : null;

  const setUpload = useCallback((line: number, progress: number | null) => {
    setUploads((current) => {
      const next = { ...current };
      if (progress === null) delete next[line];
      else next[line] = progress;
      return next;
    });
  }, []);

  const confirmNumbering = useCallback((body: ArrangeBody, preview: ArrangePreview) => {
    setDialog({ kind: "arrange", body, preview });
  }, []);

  const actions = useStudioActions({ project, setProject, refetch, confirmNumbering, setUpload });

  const started = useCallback(
    (job: Job) => {
      jobs.start(job);
      // Read once so the locks and step states reflect the job. After this only /api/job is polled.
      void refetch();
    },
    [jobs, refetch],
  );

  // Row and drop handlers are stable, so the rows stay memoised.
  const onOpen = useCallback((line: number) => setDialog({ kind: "image", line }), []);
  const onFiles = useCallback(
    (files: File[], target: DropTarget) => {
      if (files.length > 1) {
        setDialog({ kind: "images", files });
        return;
      }
      if (latest.current.images.mode === "positional") {
        toast({
          tone: "attention",
          message: "Renumber images first",
          detail: "This folder is paired by position, so an image cannot be put on one line by itself yet.",
          action: { label: "Renumber", run: () => setDialog({ kind: "renumber" }) },
        });
        return;
      }
      void actions.uploadToLine(files[0], target.line, target.op === "insert");
    },
    [actions, toast],
  );
  const onMove = useCallback(
    (image: string, _from: number, to: number) => void actions.arrange({ op: "place", image, line: to }),
    [actions],
  );
  const onNudge = useCallback(
    async (line: number, delta: -1 | 1) => {
      const board = latest.current.storyboard;
      const target = line + delta;
      const slot = board[line - 1];
      if (!slot?.image || target < 1 || target > board.length || latest.current.locked.images) return;
      await actions.arrange({ op: "place", image: slot.image.name, line: target });
      setFocus({ line: target, nonce: Date.now() });
    },
    [actions],
  );
  const onDrop = useCallback(
    (source: DragSource, target: DropTarget) =>
      void actions.arrange({ op: target.op, image: source.image, line: target.line }),
    [actions],
  );

  const focusLine = useCallback((line: number) => {
    const slot = latest.current.storyboard[line - 1];
    if (filterRef.current === "missing" && slot?.state !== "missing") setFilter("all");
    setFocus({ line, nonce: Date.now() });
  }, []);

  useEffect(() => {
    if (!focus) return;
    const go = () => {
      const element = document.getElementById(`line-${focus.line}`);
      if (!element) return;
      element.scrollIntoView({ block: "center" });
      element.focus({ preventScroll: true });
    };
    go();
    // Rows off screen have estimated heights until drawn, so settle once more.
    const frame = window.requestAnimationFrame(() => window.requestAnimationFrame(go));
    return () => window.cancelAnimationFrame(frame);
  }, [focus, filter, view]);

  const open = useCallback((next: DialogState) => () => setDialog(next), []);
  const strip = useMemo(
    () => ({
      onNarration: open({ kind: "narration" }),
      onTranscribe: open({ kind: "transcribe" }),
      onUploadTranscript: open({ kind: "upload-transcript" }),
      onEditTranscript: open({ kind: "edit-transcript" }),
      onDownloadTranscript: open({ kind: "download-transcript" }),
      onAddImages: open({ kind: "images" }),
      onBuild: open({ kind: "build" }),
      onRenumber: open({ kind: "renumber" }),
    }),
    [open],
  );

  const board = useMemo(
    () => ({ lines: project.storyboard, positional: project.images.mode === "positional", locked: lockImages }),
    [project.storyboard, project.images.mode, lockImages],
  );

  const close = useCallback(() => setDialog(null), []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link
          href="/"
          className="inline-flex w-fit items-center gap-1 rounded-[var(--radius-control)] text-sm text-muted hover:text-text"
        >
          <ChevronLeft size={16} aria-hidden />
          Projects
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <ProjectTitle project={project} onProject={setProject} />
          <Button
            variant="build"
            onClick={strip.onBuild}
            disabled={Boolean(busy)}
            title={busy ?? undefined}
          >
            {renderingHere ? "Building video" : "Build video"}
          </Button>
        </div>
      </div>

      <StatusStrip project={project} locked={locked} busy={busy} lockedReason={lockedReason} {...strip} />

      <CoverageTimeline lines={project.storyboard} seconds={project.audio.seconds} onSelect={focusLine} />

      <Banners
        project={project}
        lockedReason={lockedReason}
        onRenumber={strip.onRenumber}
        onTranscribe={strip.onTranscribe}
        busy={busy}
      />

      <ArrangeDnd board={board} onDrop={onDrop}>
        <Storyboard
          project={project}
          filter={filter}
          view={view}
          locked={lockImages}
          lockedReason={lockImages ? lockedReason : null}
          uploads={uploads}
          onFilter={setFilter}
          onView={setView}
          onRenumber={strip.onRenumber}
          onAddImages={strip.onAddImages}
          onTranscribe={strip.onTranscribe}
          onUploadTranscript={strip.onUploadTranscript}
          onNarration={strip.onNarration}
          onRemoveImage={actions.removeImage}
          transcribing={transcribingHere}
          onOpen={onOpen}
          onFiles={onFiles}
          onNudge={onNudge}
        />
      </ArrangeDnd>

      <VideosPanel
        projectId={project.id}
        videos={project.videos}
        onRemove={actions.removeVideo}
        onBuild={strip.onBuild}
        busy={busy}
        ready={project.blockers.length === 0}
      />

      {dialog?.kind === "narration" ? (
        <UploadNarrationDialog
          project={project}
          locked={lockAudio}
          lockedReason={lockedReason}
          onClose={close}
          onProject={setProject}
          refetch={refetch}
          onRemove={actions.removeAudio}
        />
      ) : null}
      {dialog?.kind === "transcribe" ? (
        <TranscribeDialog
          project={project}
          busy={busy}
          locked={lockTranscript}
          lockedReason={lockedReason}
          onClose={close}
          onStarted={started}
        />
      ) : null}
      {dialog?.kind === "upload-transcript" ? (
        <UploadTranscriptDialog
          project={project}
          locked={lockTranscript}
          lockedReason={lockedReason}
          onClose={close}
          onProject={setProject}
        />
      ) : null}
      {dialog?.kind === "edit-transcript" ? (
        <EditTranscriptDialog
          project={project}
          locked={lockTranscript}
          lockedReason={lockedReason}
          onClose={close}
          onProject={setProject}
        />
      ) : null}
      {dialog?.kind === "download-transcript" ? <DownloadTranscriptDialog project={project} onClose={close} /> : null}
      {dialog?.kind === "images" ? (
        <AddImagesDialog
          project={project}
          locked={lockImages}
          lockedReason={lockedReason}
          initialFiles={dialog.files}
          onClose={close}
          refetch={refetch}
        />
      ) : null}
      {dialog?.kind === "image" ? (
        <ImageDialog
          project={project}
          line={dialog.line}
          locked={lockImages}
          lockedReason={lockedReason}
          onClose={close}
          onReplace={(file, line) => void actions.uploadToLine(file, line, false)}
          onRemove={(name) => void actions.removeImage(name)}
          onMove={onMove}
        />
      ) : null}
      {dialog?.kind === "renumber" ? (
        <RenumberDialog
          project={project}
          locked={lockImages}
          lockedReason={lockedReason}
          onClose={close}
          onProject={setProject}
          onUndo={actions.undo}
        />
      ) : null}
      {dialog?.kind === "build" ? (
        <BuildDialog
          project={project}
          busy={busy}
          onClose={close}
          onStarted={started}
          onAddImages={() => setFilter("missing")}
        />
      ) : null}
      {dialog?.kind === "arrange" ? (
        <ArrangeConfirmDialog
          preview={dialog.preview}
          onConfirm={() => actions.runArrange(dialog.body)}
          onClose={close}
        />
      ) : null}
    </div>
  );
}
