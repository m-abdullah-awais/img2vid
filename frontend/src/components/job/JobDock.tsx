"use client";

import { ChevronDown, ChevronUp, Download, Play, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { apiUrl, projectPath } from "@/lib/api";
import { duration, prose } from "@/lib/format";
import { useNow } from "@/lib/hooks/useNow";
import type { Job } from "@/lib/types";
import { Button, buttonClass } from "../ui/Button";
import { ProgressBar } from "../ui/ProgressBar";
import { useToast } from "../ui/Toast";
import { useJob, useJobActions } from "./JobProvider";

const RECENT_MS = 10 * 60 * 1000;

/** One name per action through the whole flow: Build video, Building video, Video built. */
export function jobTitle(job: Job): string {
  const running = job.state === "running";
  switch (job.kind) {
    case "render":
      if (running) return "Building video";
      if (job.state === "done") return "Video built";
      if (job.state === "nothing") return "No video to build";
      if (job.state === "cancelled") return "Building video cancelled";
      if (job.state === "interrupted") return "Building video stopped when the engine closed";
      return "Video not built";
    case "transcribe":
      if (running) return "Transcribing narration";
      if (job.state === "done") {
        return typeof job.result?.lines === "number"
          ? `Transcript ready, ${job.result.lines} lines`
          : "Transcript ready";
      }
      if (job.state === "nothing") return "Transcript already up to date";
      if (job.state === "cancelled") return "Transcribing cancelled";
      if (job.state === "interrupted") return "Transcribing stopped when the engine closed";
      return "Transcript not made";
    case "model":
      if (running) return "Downloading speech model";
      if (job.state === "done" || job.state === "nothing") return "Speech model downloaded";
      if (job.state === "cancelled") return "Model download cancelled";
      if (job.state === "interrupted") return "Model download stopped when the engine closed";
      return "Speech model not downloaded";
    default:
      if (running) return "Running the self-test";
      if (job.state === "done" || job.state === "nothing") return "Self-test passed";
      if (job.state === "cancelled") return "Self-test cancelled";
      if (job.state === "interrupted") return "Self-test stopped when the engine closed";
      return "Self-test failed";
  }
}

function markFor(job: Job): string {
  if (job.state === "running") return "bg-text";
  if (job.state === "done" || job.state === "nothing") return "bg-ready";
  if (job.state === "failed" || job.state === "interrupted") return "bg-build";
  return "bg-muted";
}

export function JobDock() {
  const job = useJob((state) => state.job);
  const log = useJob((state) => state.log);
  const truncated = useJob((state) => state.truncated);
  const watched = useJob((state) => state.watched);
  const dismissed = useJob((state) => state.dismissed);
  const offline = useJob((state) => state.offline);
  const actions = useJobActions();
  const { toast } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const now = useNow(30_000);

  const [showLog, setShowLog] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const dock = useRef<HTMLDivElement>(null);
  const logBox = useRef<HTMLPreElement>(null);

  const running = job?.state === "running";
  const ended = job?.endedAt ? new Date(job.endedAt).getTime() : 0;
  const recent = Boolean(job && !running && (job.id === watched || (now > 0 && now - ended < RECENT_MS)));
  const visible = Boolean(job && offline !== true && dismissed !== job.id && (running || recent));

  // Everything above the dock keeps clear of it.
  useLayoutEffect(() => {
    const root = document.documentElement;
    const node = dock.current;
    if (!visible || !node) {
      root.style.setProperty("--dock-h", "0px");
      return;
    }
    const observer = new ResizeObserver(() => {
      root.style.setProperty("--dock-h", `${node.offsetHeight}px`);
    });
    observer.observe(node);
    return () => {
      observer.disconnect();
      root.style.setProperty("--dock-h", "0px");
    };
  }, [visible]);

  // Follow the log's tail, unless the reader scrolled up to look at something.
  useEffect(() => {
    const box = logBox.current;
    if (!box || !showLog) return;
    const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 48;
    if (nearBottom) box.scrollTop = box.scrollHeight;
  }, [log, showLog]);

  if (!visible || !job) return null;

  const progress = job.progress;
  const percent = progress !== null ? Math.floor(progress * 100) : null;
  const left =
    running && progress !== null && progress > 0.05 ? (job.elapsed * (1 - progress)) / progress : null;
  const video = job.result?.video;
  const summary = job.result?.summary || video?.summary || null;
  const failedText = job.state === "failed" ? prose(job.error) || "The engine stopped without saying why. Show the log for its last lines." : null;
  const onProject = job.projectId ? pathname === `/projects/${job.projectId}` : false;

  return (
    <div
      ref={dock}
      role="region"
      aria-label="Current job"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-hairline bg-panel"
    >
      <div className="mx-auto w-full max-w-[1400px] px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-6">
          <div className="flex min-w-0 items-start gap-3 lg:w-[34%] lg:shrink-0">
            <span aria-hidden className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${markFor(job)}`} />
            <div className="min-w-0">
              <p className="font-semibold" aria-live="polite">
                {jobTitle(job)}
                {job.projectName ? <span className="font-normal text-muted"> for {job.projectName}</span> : null}
              </p>
              {running ? (
                <p className="text-sm text-muted">{job.phase}</p>
              ) : failedText ? (
                <p className="line-clamp-2 text-sm text-text" title={failedText}>
                  {failedText}
                </p>
              ) : summary ? (
                <p className="line-clamp-2 text-sm text-muted" title={summary}>
                  {summary}
                </p>
              ) : null}
            </div>
          </div>

          {running ? (
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <ProgressBar value={progress} label={jobTitle(job)} />
              <div className="timecode flex flex-wrap gap-x-5 text-sm text-muted">
                {/* No percent until the engine reports one. The phase line above
                    already says what is happening, so nothing stands in for it. */}
                {percent !== null ? <span className="text-text">{percent}%</span> : null}
                <span>{duration(job.elapsed)} elapsed</span>
                {left !== null ? <span>about {duration(left)} left</span> : null}
              </div>
            </div>
          ) : (
            <div className="flex-1" />
          )}

          <div className="flex flex-wrap items-center gap-2">
            {job.state === "done" && job.kind === "render" && video && job.projectId ? (
              <>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    actions.requestPlay(job.projectId as string, video.name);
                    if (!onProject) router.push(`/projects/${job.projectId}`);
                  }}
                >
                  <Play size={15} aria-hidden />
                  Play
                </Button>
                <a className={buttonClass("secondary", "sm")} href={apiUrl(video.download)}>
                  <Download size={15} aria-hidden />
                  Download
                </a>
              </>
            ) : null}
            {/* A finished transcript is offered here the way a finished video
                is, so nobody has to go looking for the file. */}
            {job.state === "done" && job.kind === "transcribe" && job.projectId ? (
              <a
                className={buttonClass("secondary", "sm")}
                href={apiUrl(`${projectPath(job.projectId, "transcript", "download")}?format=txt`)}
              >
                <Download size={15} aria-hidden />
                Download
              </a>
            ) : null}
            {!running && job.kind === "transcribe" && job.projectId && !onProject ? (
              <Button size="sm" variant="secondary" onClick={() => router.push(`/projects/${job.projectId}`)}>
                Open project
              </Button>
            ) : null}
            <Button size="sm" variant="ghost" aria-expanded={showLog} onClick={() => setShowLog((open) => !open)}>
              {showLog ? <ChevronDown size={15} aria-hidden /> : <ChevronUp size={15} aria-hidden />}
              {showLog ? "Hide log" : "Show log"}
            </Button>
            {running ? (
              <Button
                size="sm"
                variant="secondary"
                disabled={cancelling}
                onClick={async () => {
                  setCancelling(true);
                  try {
                    await actions.cancel();
                  } catch (error) {
                    toast({ tone: "error", message: "Could not cancel", detail: (error as Error).message });
                  } finally {
                    setCancelling(false);
                  }
                }}
              >
                {cancelling ? "Cancelling" : "Cancel"}
              </Button>
            ) : (
              <button
                type="button"
                onClick={() => actions.dismiss(job.id)}
                aria-label="Close"
                title="Close"
                className="inline-flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-muted hover:bg-graphite hover:text-text"
              >
                <X size={16} aria-hidden />
              </button>
            )}
          </div>
        </div>

        {showLog ? (
          <div className="mt-3">
            {truncated ? (
              <p className="mb-1 text-xs text-muted">Earlier lines were dropped. The engine keeps the last 2000.</p>
            ) : null}
            <pre
              ref={logBox}
              tabIndex={0}
              aria-label="Job log"
              className="timecode max-h-[38vh] overflow-auto rounded-[var(--radius-control)] border border-hairline bg-graphite p-3 text-xs leading-relaxed whitespace-pre-wrap text-muted"
            >
              {log.length ? log.join("\n") : "No output yet."}
            </pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}
