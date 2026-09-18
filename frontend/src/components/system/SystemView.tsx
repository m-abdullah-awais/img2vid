"use client";

import { Download, Play } from "lucide-react";
import { useCallback, useState, type ReactNode } from "react";
import { post, toApiError } from "@/lib/api";
import { bytes, plural } from "@/lib/format";
import { useSystem } from "@/lib/hooks/useSystem";
import type { Job, ModelName, SystemInfo } from "@/lib/types";
import { jobTitle } from "../job/JobDock";
import { busyReason, useEngineOnline, useJob, useJobActions, useJobFinished, useRunning } from "../job/JobProvider";
import { Banner } from "../studio/Banners";
import { Button } from "../ui/Button";
import { EngineDown } from "../ui/EngineDown";
import { ProgressBar } from "../ui/ProgressBar";
import { useToast } from "../ui/Toast";

type Health = "ready" | "attention" | "error" | "idle";

const dots: Record<Health, string> = {
  ready: "bg-ready",
  attention: "bg-missing",
  error: "bg-build",
  idle: "border border-muted",
};

function Row({ label, health, children }: { label: string; health: Health; children: ReactNode }) {
  return (
    <div className="grid gap-x-6 gap-y-1 py-3 sm:grid-cols-[13rem_minmax(0,1fr)]">
      <dt className="flex items-center gap-2.5 font-semibold">
        <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full ${dots[health]}`} />
        {label}
      </dt>
      <dd className="min-w-0 text-sm">{children}</dd>
    </div>
  );
}

function Path({ value }: { value: string | null }) {
  if (!value) return null;
  return <p className="timecode break-all text-muted">{value}</p>;
}

const MODEL_NOTES: Record<ModelName, string> = {
  tiny: "Fastest and roughest.",
  base: "Accurate on clear narration, and several times faster than it plays.",
  small: "Much slower, and on this computer no more accurate than base.",
};

export function SystemView() {
  const { system, error, refetch } = useSystem();
  const engineDown = useJob((state) => state.offline === true);
  const jobs = useJobActions();
  const running = useRunning();
  const busy = busyReason(running);
  const { toast } = useToast();
  const [starting, setStarting] = useState<string | null>(null);

  useJobFinished((job) => {
    if (job.kind === "model" || job.kind === "check") void refetch();
  });
  useEngineOnline(() => void refetch());

  const start = useCallback(
    async (key: string, path: string, body: unknown) => {
      setStarting(key);
      try {
        const { job } = await post<{ job: Job }>(path, body);
        jobs.start(job);
      } catch (failure) {
        toast({ tone: "error", message: "Did not start", detail: toApiError(failure).message });
      } finally {
        setStarting(null);
      }
    },
    [jobs, toast],
  );

  if (engineDown || (error?.code === "unreachable" && !system)) {
    return (
      <EngineDown
        onRetry={async () => {
          jobs.refresh();
          await refetch();
        }}
      />
    );
  }

  return (
    <div className="flex max-w-[1040px] flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="heading text-3xl">System</h1>
        <p className="max-w-[70ch] text-muted">
          What the engine found on this computer. Installing Python, ffmpeg or the speech engine is
          Setup.bat&apos;s job: close img2vid, run Setup.bat, then start img2vid again with Run.bat.
        </p>
      </div>

      {error && error.code !== "unreachable" ? (
        <Banner tone="error" title="The system report could not be read" actions={<Button size="sm" onClick={() => void refetch()}>Retry</Button>}>
          {error.message}
        </Banner>
      ) : null}

      {!system ? (
        <p className="text-sm text-muted" aria-live="polite">
          Reading the system report
        </p>
      ) : (
        <>
          <Tools system={system} />
          <Models
            system={system}
            busy={busy}
            starting={starting}
            onDownload={(model) => void start(`model:${model}`, "/api/system/model", { model })}
          />
          <Storage system={system} />
        </>
      )}

      <SelfTest busy={busy} starting={starting === "check"} onRun={() => void start("check", "/api/system/check", {})} />
    </div>
  );
}

function Tools({ system }: { system: SystemInfo }) {
  const { python, ffmpeg, node, encoder, speech, guard } = system;
  return (
    <section aria-labelledby="tools-title" className="flex flex-col gap-2">
      <h2 id="tools-title" className="heading text-2xl">
        Tools
      </h2>
      <dl className="divide-y divide-hairline border-y border-hairline">
        <Row label="Python" health="ready">
          <p>
            <span className="timecode">{python.version}</span>
            <span className="text-muted">, {python.source === "runtime" ? "the private copy Setup.bat unpacked" : "found on PATH"}</span>
          </p>
          <Path value={python.path} />
        </Row>
        <Row label="ffmpeg" health={ffmpeg.found ? "ready" : "error"}>
          {ffmpeg.found ? (
            <>
              <p className="text-muted">{ffmpeg.source === "runtime" ? "The private copy Setup.bat unpacked" : "Found on PATH"}</p>
              <Path value={ffmpeg.path} />
            </>
          ) : (
            <p>Not found. Videos cannot be built without it. Run Setup.bat, which fetches a private copy.</p>
          )}
        </Row>
        <Row label="Node.js" health={node.version ? "ready" : "attention"}>
          {node.version ? (
            <>
              <p className="timecode">{node.version}</p>
              <Path value={node.path} />
            </>
          ) : (
            <p>Not found by the engine. This page is served by Node, so Run.bat found one; Setup.bat can install a private copy.</p>
          )}
        </Row>
        <Row label="Video encoder" health={encoder ? "ready" : "idle"}>
          {encoder ? (
            <p>
              <span className="timecode">{encoder.name}</span>
              {encoder.fps ? <span className="timecode text-muted">, measured at {Math.round(encoder.fps)} frames a second</span> : null}
            </p>
          ) : (
            <p className="text-muted">Not measured yet. The first build times the encoders on this computer and keeps the fastest.</p>
          )}
        </Row>
        <Row
          label="Speech engine"
          health={!speech.installed ? "attention" : speech.matches ? "ready" : "error"}
        >
          {!speech.installed ? (
            <p>Not installed. Transcribing needs it; building videos does not. Run Setup.bat to install it.</p>
          ) : speech.matches ? (
            <p>
              Installed, built for Python <span className="timecode">{speech.builtFor ?? python.version}</span>, which
              matches.
            </p>
          ) : (
            <p>
              Built for Python <span className="timecode">{speech.builtFor ?? "unknown"}</span>, but the engine runs
              Python <span className="timecode">{python.version}</span>. Run Setup.bat to rebuild it for this Python.
            </p>
          )}
        </Row>
        <Row label="Process guard" health={guard ? "ready" : "attention"}>
          <p className={guard ? "text-muted" : ""}>
            {guard
              ? "On. Closing the img2vid window stops every encoder with it."
              : "Off. An encoder could keep running if img2vid is closed during a build."}
          </p>
        </Row>
      </dl>
    </section>
  );
}

function Models({
  system,
  busy,
  starting,
  onDownload,
}: {
  system: SystemInfo;
  busy: string | null;
  starting: string | null;
  onDownload: (model: ModelName) => void;
}) {
  return (
    <section aria-labelledby="models-title" className="flex flex-col gap-2">
      <h2 id="models-title" className="heading text-2xl">
        Speech models
      </h2>
      <p className="max-w-[70ch] text-sm text-muted">
        Transcribing downloads the chosen model the first time. Download one here ahead of time, for
        example before going offline.
      </p>
      <ul className="divide-y divide-hairline border-y border-hairline">
        {system.speech.models.map((model) => (
          <li key={model.name} className="flex flex-wrap items-center gap-x-6 gap-y-2 py-3">
            <div className="min-w-0 flex-1">
              <p className="font-semibold">
                {model.name}
                {model.name === system.speech.default ? <span className="font-normal text-muted">, the default</span> : null}
              </p>
              <p className="text-sm text-muted">{model.note || MODEL_NOTES[model.name]}</p>
            </div>
            {model.local ? (
              <p className="flex items-center gap-2 text-sm">
                <span aria-hidden className="h-2 w-2 rounded-full bg-ready" />
                On this computer
              </p>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                disabled={Boolean(busy) || starting !== null || !system.speech.installed}
                title={busy ?? (!system.speech.installed ? "Install the speech engine with Setup.bat first" : undefined)}
                onClick={() => onDownload(model.name)}
              >
                <Download size={15} aria-hidden />
                {starting === `model:${model.name}` ? "Starting" : "Download"}
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Storage({ system }: { system: SystemInfo }) {
  const { storage } = system;
  return (
    <section aria-labelledby="storage-title" className="flex flex-col gap-2">
      <h2 id="storage-title" className="heading text-2xl">
        Storage
      </h2>
      <dl className="divide-y divide-hairline border-y border-hairline">
        <Row label="In use" health="idle">
          <p>
            <span className="timecode">{bytes(storage.bytes)}</span>
            <span className="text-muted">, across {plural(storage.projects, "project")}, trash included</span>
          </p>
        </Row>
        <Row label="Trash" health="idle">
          <p>
            <span className="timecode">{bytes(storage.trashBytes)}</span>
            <span className="text-muted">. Anything removed stays restorable for 7 days, then is deleted.</span>
          </p>
        </Row>
      </dl>
    </section>
  );
}

function SelfTest({ busy, starting, onRun }: { busy: string | null; starting: boolean; onRun: () => void }) {
  const job = useJob((state) => (state.job?.kind === "check" ? state.job : null));
  const log = useJob((state) => (state.job?.kind === "check" ? state.log : null));
  const runningHere = job?.state === "running";
  return (
    <section aria-labelledby="check-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="check-title" className="heading text-2xl">
            Self-test
          </h2>
          <p className="max-w-[70ch] text-sm text-muted">
            Builds a four second video from test colours it makes itself, then checks it frame by frame,
            along with the speech engine. It proves this computer can make a correct video.
          </p>
        </div>
        <Button variant="secondary" onClick={onRun} disabled={Boolean(busy) || starting} title={busy ?? undefined}>
          <Play size={15} aria-hidden />
          {starting ? "Starting" : runningHere ? "Running self-test" : "Run self-test"}
        </Button>
      </div>
      {job ? (
        <div className="flex flex-col gap-2">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <span
              aria-hidden
              className={`h-2 w-2 rounded-full ${
                runningHere ? "bg-text" : job.state === "done" || job.state === "nothing" ? "bg-ready" : job.state === "failed" ? "bg-build" : "bg-muted"
              }`}
            />
            {jobTitle(job)}
            {runningHere ? <span className="font-normal text-muted">, {job.phase}</span> : null}
          </p>
          {runningHere ? <ProgressBar value={job.progress} label="Self-test" /> : null}
          {job.state === "failed" && job.error ? <p className="text-sm">{job.error}</p> : null}
          <pre
            tabIndex={0}
            aria-label="Self-test log"
            className="timecode max-h-[50vh] overflow-auto rounded-[var(--radius-control)] border border-hairline bg-panel p-3 text-xs leading-relaxed whitespace-pre-wrap text-muted"
          >
            {log && log.length ? log.join("\n") : "No output yet."}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
