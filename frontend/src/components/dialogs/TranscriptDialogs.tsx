"use client";

import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { api, apiUrl, projectPath, request, toApiError, upload, type ApiError } from "@/lib/api";
import { plural } from "@/lib/format";
import type { Blocker, Project, TranscriptRaw, TranscriptResult } from "@/lib/types";
import { Banner } from "../studio/Banners";
import { Button, buttonClass } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { TextArea } from "../ui/Field";
import { useToast } from "../ui/Toast";
import { DropZone } from "./DropZone";

type Common = {
  project: Project;
  onClose: () => void;
};

type Editable = Common & {
  locked: boolean;
  lockedReason: string | null;
  onProject: (project: Project) => void;
};

function blockersOf(error: ApiError): Blocker[] {
  const list = (error.details as { blockers?: Blocker[] } | null)?.blockers;
  return Array.isArray(list) ? list : [];
}

function useLineShiftToast() {
  const { toast } = useToast();
  return (result: TranscriptResult, verb: string) => {
    const { linesBefore, linesAfter, project } = result;
    const changed = linesBefore > 0 && linesBefore !== linesAfter && project.images.total > 0;
    toast({
      tone: changed ? "attention" : "done",
      message: `${verb}, ${plural(linesAfter, "line")}`,
      detail: changed
        ? `It had ${linesBefore}. Images stay on their numbers while the narration moves under them, so check the storyboard.`
        : undefined,
      duration: changed ? 12000 : undefined,
    });
  };
}

/** A transcript made elsewhere: .srt, .vtt or .txt. Read first; nothing changes if it cannot be. */
export function UploadTranscriptDialog({ project, locked, lockedReason, onClose, onProject }: Editable) {
  const report = useLineShiftToast();
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<{ message: string; blockers: Blocker[] } | null>(null);

  async function send() {
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      const result = await upload<TranscriptResult>(projectPath(project.id, "transcript", file.name), file, {
        onProgress: setProgress,
      });
      onProject(result.project);
      report(result, "Transcript uploaded");
      onClose();
    } catch (failure) {
      const apiError = toApiError(failure);
      setError({ message: apiError.message, blockers: blockersOf(apiError) });
      setProgress(null);
    }
  }

  const sending = progress !== null;

  return (
    <Dialog
      title="Upload transcript"
      onClose={onClose}
      dismissible={!sending}
      description="A transcript with timings, as SRT, VTT or TXT. Each of its lines gets one image."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={sending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => void send()} disabled={!file || sending || locked}>
            {sending ? "Uploading" : "Upload transcript"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {locked ? <Banner tone="info" title="The transcript is locked">{lockedReason}</Banner> : null}
        <DropZone
          accept=".srt,.vtt,.txt"
          disabled={locked || sending}
          onFiles={(files) => {
            setFile(files[0] ?? null);
            setError(null);
          }}
          title={file ? file.name : "Drop a transcript here, or choose one"}
          hint={file ? "Choose again to pick a different file." : ".srt, .vtt or .txt, up to 5 MB."}
        />
        {project.transcript ? (
          <Banner tone="attention" title={`This replaces the current transcript, ${plural(project.transcript.lines, "line")}`}>
            The old one goes to the trash and can be restored for 7 days.
          </Banner>
        ) : null}
        {error ? (
          <Banner tone="error" title="The transcript was not used">
            {error.blockers.length ? (
              <ul className="flex flex-col gap-1">
                {error.blockers.map((blocker) => (
                  <li key={blocker.code + blocker.message}>{blocker.message}</li>
                ))}
              </ul>
            ) : (
              error.message
            )}
          </Banner>
        ) : null}
      </div>
    </Dialog>
  );
}

/** Rough line count while typing, to warn before saving. The API's count is the real one. */
function countLines(text: string, name: string): number {
  const cues = text.match(/-->/g)?.length ?? 0;
  if (cues || /\.(srt|vtt)$/i.test(name)) return cues;
  return text.split(/\r?\n/).filter((line) => line.trim()).length;
}

/** The transcript as text. Saved only if nobody changed it since it was opened. */
export function EditTranscriptDialog({ project, locked, lockedReason, onClose, onProject }: Editable) {
  const report = useLineShiftToast();
  const [raw, setRaw] = useState<TranscriptRaw | null>(null);
  const [text, setText] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<{ message: string; changed: boolean } | null>(null);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let alive = true;
    api<TranscriptRaw>(projectPath(project.id, "transcript", "raw"))
      .then((data) => {
        if (!alive) return;
        setRaw(data);
        setText(data.text);
        setLoadError(null);
        setSaveError(null);
      })
      .catch((failure) => {
        if (alive) setLoadError(toApiError(failure).message);
      });
    return () => {
      alive = false;
    };
  }, [project.id, reload]);

  const before = project.transcript?.lines ?? 0;
  const after = raw ? countLines(text, raw.name) : before;
  const dirty = raw !== null && text !== raw.text;

  async function save() {
    if (!raw) return;
    setSaving(true);
    setSaveError(null);
    try {
      const result = await request<TranscriptResult>(projectPath(project.id, "transcript", "raw"), {
        method: "PUT",
        json: { text, version: raw.version },
      });
      if (result.data) {
        onProject(result.data.project);
        report(result.data, "Transcript saved");
      }
      onClose();
    } catch (failure) {
      const apiError = toApiError(failure);
      setSaveError({ message: apiError.message, changed: apiError.code === "changed" });
      setSaving(false);
    }
  }

  return (
    <Dialog
      title="Edit transcript"
      size="xl"
      onClose={onClose}
      dismissible={!saving}
      description={raw ? raw.name : "Loading the transcript"}
      footer={
        <>
          <span className="timecode mr-auto text-sm text-muted">
            {raw ? `${plural(after, "line")}${after !== before ? `, was ${before}` : ""}` : ""}
          </span>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => void save()} disabled={!dirty || saving || locked}>
            {saving ? "Saving" : "Save transcript"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {locked ? <Banner tone="info" title="The transcript is locked">{lockedReason}</Banner> : null}
        {loadError ? <Banner tone="error" title="The transcript could not be opened">{loadError}</Banner> : null}
        {raw && after !== before ? (
          <Banner tone="attention" title={`The line count changes from ${before} to ${after}`}>
            Numbered images stay on their number while the narration moves under them. Image 12 stays on
            line 12 even if line 12 now says something else, so check the storyboard after saving.
          </Banner>
        ) : null}
        {saveError ? (
          <Banner
            tone="error"
            title={saveError.changed ? "The transcript changed since you opened it" : "Not saved"}
            actions={
              saveError.changed ? (
                <Button size="sm" variant="secondary" onClick={() => setReload((count) => count + 1)}>
                  Load the new version
                </Button>
              ) : null
            }
          >
            {saveError.changed
              ? `${saveError.message} Copy your edits first if you want to keep them: loading the new version replaces them.`
              : saveError.message}
          </Banner>
        ) : null}
        <label htmlFor="transcript-text" className="sr-only">
          Transcript text
        </label>
        <TextArea
          id="transcript-text"
          value={text}
          disabled={!raw || locked}
          spellCheck
          rows={22}
          onChange={(event) => setText(event.target.value)}
          className="timecode min-h-[50vh] resize-y text-sm leading-relaxed"
        />
      </div>
    </Dialog>
  );
}

/** The transcript as a file, for YouTube captions or a script. */
export function DownloadTranscriptDialog({ project, onClose }: Common) {
  const base = projectPath(project.id, "transcript", "download");
  const options = [
    { key: "srt", href: `${base}?format=srt`, title: "SRT captions", body: "Timed lines. YouTube accepts it as a captions file.", label: "SRT" },
    { key: "txt", href: `${base}?format=txt`, title: "Plain text", body: "The lines as text, for a script or a video description.", label: "TXT" },
    ...(project.transcript
      ? [
          {
            key: "original",
            href: project.transcript.url || base,
            title: "The original file",
            body: `${project.transcript.name}, exactly as it was saved.`,
            label: "Original",
          },
        ]
      : []),
  ];
  return (
    <Dialog title="Download transcript" size="sm" onClose={onClose}>
      <ul className="flex flex-col gap-2">
        {options.map((option) => (
          <li key={option.key} className="flex items-center gap-3 rounded-[var(--radius-control)] border border-hairline px-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{option.title}</p>
              <p className="text-sm break-words text-muted">{option.body}</p>
            </div>
            <a
              className={buttonClass("secondary", "sm")}
              href={apiUrl(option.href)}
              onClick={() => window.setTimeout(onClose, 300)}
            >
              <Download size={15} aria-hidden />
              <span className="sr-only">Download as </span>
              {option.label}
            </a>
          </li>
        ))}
      </ul>
    </Dialog>
  );
}
