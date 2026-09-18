// The img2vid API contract, v1. Field names and shapes mirror
// temp/api-contract.md exactly; the backend is written against the same file.

export type Tone = "ready" | "attention" | "missing" | "busy" | "idle";

export type ProjectSummary = {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  cover: string | null;
  status: { text: string; tone: Tone };
  counts: { lines: number; images: number; missing: number; videos: number };
  seconds: number | null;
};

export type StepState = "missing" | "ready" | "attention" | "busy";

export type Step = {
  state: StepState;
  summary: string;
  detail: string | null;
};

export type ImageRef = {
  name: string;
  url: string;
  thumb: string;
  bytes: number;
  version: string;
};

export type LineState = "ok" | "missing" | "duplicate";

export type Line = {
  line: number;
  number: number;
  start: number;
  end: number;
  seconds: number;
  text: string;
  state: LineState;
  image: ImageRef | null;
};

export type Video = {
  name: string;
  bytes: number;
  seconds: number;
  createdAt: string;
  url: string;
  download: string;
  outdated: boolean;
  summary: string | null;
};

export type Gate = {
  repair: "--allow-black" | "--force";
  question: string;
  message: string;
  missing?: number[];
};

export type Blocker = { code: string; message: string };

export type JobKind = "transcribe" | "render" | "check" | "model";
export type JobState = "running" | "done" | "nothing" | "failed" | "cancelled" | "interrupted";

export type Job = {
  id: string;
  kind: JobKind;
  projectId: string | null;
  projectName: string | null;
  state: JobState;
  phase: string;
  progress: number | null;
  startedAt: string;
  endedAt: string | null;
  elapsed: number;
  exitCode: number | null;
  error: string | null;
  result: { video?: Video; lines?: number; summary?: string } | null;
};

export type RenderSettings = {
  fps: number;
  size: string;
  fit: "contain" | "cover";
  background: string;
};

export type AudioFile = { name: string; bytes: number; seconds: number | null; url: string };

export type PositionalReason = {
  kind: "unnumbered" | "past_end" | "no_lines";
  name: string | null;
  number: number | null;
};

export type Project = {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  version: string;
  steps: { narration: Step; transcript: Step; images: Step; video: Step };
  audio: { files: AudioFile[]; seconds: number | null };
  transcript: { name: string; lines: number; stale: boolean; url: string } | null;
  images: {
    mode: "numbered" | "positional" | "empty";
    reason: PositionalReason | null;
    base: 0 | 1;
    width: number;
    total: number;
    placed: number;
    missing: number[];
    duplicates: { line: number; names: string[] }[];
    unplaced: ImageRef[];
  };
  storyboard: Line[];
  gates: Gate[];
  blockers: Blocker[];
  videos: Video[];
  settings: RenderSettings;
  job: Job | null;
  locked: { audio: boolean; transcript: boolean; images: boolean };
};

// Response bodies

export type ProjectEnvelope = { project: Project };
export type TrashResult = { trashId: string; project: Project };
export type RestoreResult = { kind: string; projectId: string; project: Project | null };

export type LineImageResult = {
  saved: string;
  trashId: string | null;
  undoId: string | null;
  project: Project;
};

export type TranscriptResult = { project: Project; linesBefore: number; linesAfter: number };
export type TranscriptRaw = { name: string; text: string; version: string };

export type LogLine = { seq: number; text: string };

export type JobPoll = {
  job: Job | null;
  events: LogLine[];
  next: number;
  truncated: boolean;
};

export type ArrangeOp = "place" | "insert";
export type ArrangeBody = { op: ArrangeOp; image: string; line: number };

export type Change = {
  from: string;
  to: string;
  lineBefore: number | null;
  lineAfter: number | null;
};

export type ArrangePreview = {
  allowed: boolean;
  reason: string | null;
  summary: string;
  numbersFolder: boolean;
  changes: Change[];
};

export type ArrangeResult = {
  undoId: string;
  summary: string;
  changes: Change[];
  project: Project;
};

export type RenameBy = "created" | "modified" | "name" | "size" | "type" | "random";

export type RenameBody = {
  by?: RenameBy | null;
  desc?: boolean;
  seed?: number | null;
  start?: number;
  digits?: number;
};

export type RenamePreview = {
  order: {
    by: RenameBy | null;
    desc: boolean;
    seed: number | null;
    label: string;
    kept: { wouldHave: string; first: string } | null;
  };
  pairs: Change[];
  changing: number;
  shifted: { count: number; first: number } | null;
  planId: string;
};

export type ModelName = "tiny" | "base" | "small";

export type SystemInfo = {
  python: { version: string; path: string; source: "runtime" | "path" };
  ffmpeg: { found: boolean; path: string | null; source: "runtime" | "path" | null };
  node: { version: string | null; path: string | null };
  encoder: { name: string; fps: number | null } | null;
  speech: {
    installed: boolean;
    builtFor: string | null;
    matches: boolean;
    models: { name: ModelName; local: boolean; note: string }[];
    default: string;
  };
  storage: { bytes: number; projects: number; trashBytes: number };
  guard: boolean;
};

export type TranscribeBody = {
  model?: ModelName;
  language?: string | null;
  maxChars?: number;
  maxSeconds?: number;
  minSeconds?: number;
  fresh?: boolean;
};

export type RenderBody = RenderSettings & {
  allowBlack?: boolean;
  force?: boolean;
  confirmedMissing?: number[];
};
