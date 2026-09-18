"use client";

import { useState } from "react";
import { post, projectPath, toApiError } from "@/lib/api";
import { paragraphs, plural, prose, snippet, timecode } from "@/lib/format";
import type { Blocker, Gate, Job, Project, RenderBody, RenderSettings } from "@/lib/types";
import { Banner } from "../studio/Banners";
import { Button } from "../ui/Button";
import { Choice } from "../ui/Field";
import { Dialog } from "../ui/Dialog";

type Props = {
  project: Project;
  busy: string | null;
  onClose: () => void;
  onStarted: (job: Job) => void;
  /** "Add images first": close, and show the lines that need them. */
  onAddImages: () => void;
};

type Flags = Pick<RenderBody, "allowBlack" | "force" | "confirmedMissing">;

type Stage =
  | { kind: "settings" }
  | { kind: "gate"; gates: Gate[]; index: number }
  | { kind: "blocked"; blockers: Blocker[] };

type Colour = "black" | "white" | "custom";

const SIZES = [
  { value: "1920x1080", label: "1920 x 1080" },
  { value: "1280x720", label: "1280 x 720" },
  { value: "1080x1920", label: "1080 x 1920 vertical" },
];

function colourOf(background: string): Colour {
  if (background === "black" || background === "white") return background;
  return "custom";
}

/** Settings, then any question the engine has, then the build. */
export function BuildDialog({ project, busy, onClose, onStarted, onAddImages }: Props) {
  const [settings, setSettings] = useState<RenderSettings>(() => ({
    fps: project.settings.fps || 30,
    size: project.settings.size || "1920x1080",
    fit: project.settings.fit || "contain",
    background: project.settings.background || "black",
  }));
  const [colour, setColour] = useState<Colour>(() => colourOf(project.settings.background || "black"));
  const [custom, setCustom] = useState(() =>
    /^#[0-9a-f]{6}$/i.test(project.settings.background) ? project.settings.background : "#1b1f24",
  );
  const [stage, setStage] = useState<Stage>({ kind: "settings" });
  const [flags, setFlags] = useState<Flags>({});
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lines = project.storyboard;
  const background = colour === "custom" ? custom : colour;

  async function send(withFlags: Flags) {
    setSending(true);
    setError(null);
    try {
      const body: RenderBody = { ...settings, background, ...withFlags };
      const { job } = await post<{ job: Job }>(projectPath(project.id, "render"), body);
      onStarted(job);
      onClose();
    } catch (failure) {
      const apiError = toApiError(failure);
      setSending(false);
      if (apiError.code === "needs_confirmation") {
        const gates = (apiError.details as { gates?: Gate[] } | null)?.gates ?? [];
        if (gates.length) {
          setFlags(withFlags);
          setStage({ kind: "gate", gates, index: 0 });
          return;
        }
      }
      if (apiError.code === "blocked") {
        const blockers = (apiError.details as { blockers?: Blocker[] } | null)?.blockers ?? [];
        setStage({ kind: "blocked", blockers: blockers.length ? blockers : [{ code: "blocked", message: apiError.message }] });
        return;
      }
      setError(apiError.message);
    }
  }

  function confirm(gate: Gate, gates: Gate[], index: number) {
    const next: Flags =
      gate.repair === "--allow-black"
        ? { ...flags, allowBlack: true, confirmedMissing: gate.missing ?? project.images.missing }
        : { ...flags, force: true };
    setFlags(next);
    if (index + 1 < gates.length) setStage({ kind: "gate", gates, index: index + 1 });
    else void send(next);
  }

  // ---- A question from the engine ----
  if (stage.kind === "gate") {
    const gate = stage.gates[stage.index];
    const black = gate.repair === "--allow-black";
    const missing = gate.missing ?? project.images.missing;
    const count = missing.length;
    const title = black
      ? `${count === 1 ? "1 line has" : `${count} lines have`} no image and will be black`
      : prose(gate.question) || "Build it anyway?";
    return (
      <Dialog
        key={`gate-${stage.index}`}
        title={title}
        size="lg"
        onClose={onClose}
        dismissible={!sending}
        footer={
          black ? (
            <>
              <Button
                variant="secondary"
                disabled={sending}
                onClick={() => {
                  onAddImages();
                  onClose();
                }}
              >
                Add images first
              </Button>
              <Button variant="build" disabled={sending} onClick={() => confirm(gate, stage.gates, stage.index)}>
                {sending ? "Starting" : `Build with ${count === 1 ? "1 black line" : `${count} black lines`}`}
              </Button>
            </>
          ) : (
            <>
              <Button variant="secondary" disabled={sending} onClick={() => setStage({ kind: "settings" })}>
                Go back
              </Button>
              <Button variant="build" disabled={sending} onClick={() => confirm(gate, stage.gates, stage.index)}>
                {sending ? "Starting" : "Build anyway"}
              </Button>
            </>
          )
        }
      >
        {black ? (
          <div className="flex flex-col gap-4">
            <p className="max-w-[68ch] text-sm text-muted">
              Images are placed by the number their filename starts with, so nothing else has moved out of
              place. Add the missing images first, or build now and leave {count === 1 ? "that line" : "those lines"} as
              a black screen while the narration plays.
            </p>
            <ol className="divide-y divide-hairline rounded-[var(--radius-control)] border border-hairline">
              {missing.map((number) => {
                const line = lines[number - 1];
                return (
                  <li key={number} className="grid grid-cols-[3.5rem_4.5rem_minmax(0,1fr)] items-baseline gap-3 px-3 py-2 text-sm">
                    <span className="timecode text-missing">Line {number}</span>
                    <span className="timecode text-muted">{line ? timecode(line.start) : ""}</span>
                    <span className="break-words">{line ? snippet(line.text, 140) : ""}</span>
                  </li>
                );
              })}
            </ol>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="max-w-[68ch] text-base whitespace-pre-line">{paragraphs(gate.message)}</p>
            <p className="max-w-[68ch] text-sm text-muted">
              Build anyway lets the engine repair this the way it describes, and the log says what it did.
              The video still runs exactly as long as the narration.
            </p>
          </div>
        )}
        {error ? (
          <div className="mt-4">
            <Banner tone="error" title="Building video did not start">{error}</Banner>
          </div>
        ) : null}
      </Dialog>
    );
  }

  // ---- Something no confirmation can fix ----
  if (stage.kind === "blocked") {
    return (
      <Dialog
        key="blocked"
        title="This video cannot be built yet"
        size="md"
        onClose={onClose}
        footer={
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        }
      >
        <ul className="flex flex-col gap-2">
          {stage.blockers.map((blocker) => (
            <li key={blocker.code + blocker.message} className="flex items-start gap-2.5 text-sm">
              <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-build" />
              <span>{blocker.message}</span>
            </li>
          ))}
        </ul>
      </Dialog>
    );
  }

  // ---- Settings ----
  const blockers = project.blockers;
  const blackGate = project.gates.find((gate) => gate.repair === "--allow-black");
  return (
    <Dialog
      key="settings"
      title="Build video"
      size="md"
      onClose={onClose}
      dismissible={!sending}
      description={`${project.name}, ${plural(lines.length, "line")}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={sending}>
            Cancel
          </Button>
          <Button
            variant="build"
            onClick={() => void send({})}
            disabled={sending || Boolean(busy) || blockers.length > 0}
            title={busy ?? undefined}
          >
            {sending ? "Starting" : "Build video"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {busy ? <Banner tone="info" title="The engine is busy">{busy}</Banner> : null}
        {blockers.length ? (
          <Banner tone="error" title="This video cannot be built yet">
            <ul className="flex flex-col gap-1">
              {blockers.map((blocker) => (
                <li key={blocker.code + blocker.message}>{blocker.message}</li>
              ))}
            </ul>
          </Banner>
        ) : null}

        <Choice<number>
          legend="Frame rate"
          value={settings.fps}
          onChange={(fps) => setSettings((current) => ({ ...current, fps }))}
          hint="15 builds about twice as fast as 30 and is fine for still images."
          options={[30, 25, 24, 15].map((fps) => ({ value: fps, label: <span className="timecode">{fps} fps</span> }))}
        />

        <Choice<string>
          legend="Size"
          value={settings.size}
          onChange={(size) => setSettings((current) => ({ ...current, size }))}
          options={SIZES.map((size) => ({ value: size.value, label: <span className="timecode">{size.label}</span> }))}
        />

        <Choice<"contain" | "cover">
          legend="Fit"
          value={settings.fit}
          onChange={(fit) => setSettings((current) => ({ ...current, fit }))}
          hint={
            settings.fit === "contain"
              ? "Letterbox shows each whole image and fills the rest of the frame with the letterbox colour."
              : "Fill and crop covers the whole frame and trims whatever sticks out."
          }
          options={[
            { value: "contain", label: "Letterbox" },
            { value: "cover", label: "Fill and crop" },
          ]}
        />

        {settings.fit === "contain" ? (
          <div className="flex flex-wrap items-end gap-3">
            <Choice<Colour>
              legend="Letterbox colour"
              value={colour}
              onChange={setColour}
              options={[
                { value: "black", label: "Black" },
                { value: "white", label: "White" },
                { value: "custom", label: "Other" },
              ]}
            />
            {colour === "custom" ? (
              <label className="mb-1 flex items-center gap-2 text-sm">
                <input
                  type="color"
                  value={custom}
                  onChange={(event) => setCustom(event.target.value)}
                  className="h-9 w-12 cursor-pointer rounded-[var(--radius-control)] border border-hairline bg-graphite p-1"
                  aria-label="Letterbox colour"
                />
                <span className="timecode text-muted">{custom.toUpperCase()}</span>
              </label>
            ) : null}
          </div>
        ) : null}

        {blackGate && !blockers.length ? (
          <p className="flex items-start gap-2 text-sm text-muted">
            <span aria-hidden className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-missing" />
            {plural(blackGate.missing?.length ?? project.images.missing.length, "line")} still{" "}
            {(blackGate.missing?.length ?? project.images.missing.length) === 1 ? "has" : "have"} no image. You will
            be asked before any line is built black.
          </p>
        ) : null}

        {error ? <Banner tone="error" title="Building video did not start">{error}</Banner> : null}
      </div>
    </Dialog>
  );
}
