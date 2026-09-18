"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { api, post } from "@/lib/api";
import type { Job, JobPoll } from "@/lib/types";

// One job runs at a time across every project, and it saturates the CPU. So
// this provider is the only thing that polls while a job runs: GET /api/job
// every 500 ms, every 4 s when idle, and not at all while the tab is hidden.
// State lives in a small external store, so a component re-renders only when
// the slice it selected changes, never the whole page on every poll.

const FAST = 500;
const IDLE = 4000;
const LOG_LIMIT = 2000;

export type JobSnapshot = {
  job: Job | null;
  log: string[];
  /** Lines were dropped from the engine's ring before they could be read. */
  truncated: boolean;
  /** null until the first answer, then whether the engine answered. */
  offline: boolean | null;
  /** A job this tab watched running, so the dock can report how it ended. */
  watched: string | null;
  dismissed: string | null;
  play: { projectId: string; name: string; nonce: number } | null;
};

const initial: JobSnapshot = {
  job: null,
  log: [],
  truncated: false,
  offline: null,
  watched: null,
  dismissed: null,
  play: null,
};

type Listener = () => void;

class JobStore {
  private state: JobSnapshot = initial;
  private listeners = new Set<Listener>();
  private finished = new Set<(job: Job) => void>();
  private online = new Set<Listener>();
  since = 0;
  private poker: () => void = () => {};

  /** The provider's loop registers how to poll right now. */
  setPoke(poke: () => void) {
    this.poker = poke;
  }

  poke() {
    this.poker();
  }

  /** A new job's log starts empty on the engine too, so read it from the top. */
  startJob(job: Job) {
    this.since = 0;
    this.set({ job, log: [], truncated: false, watched: job.id, dismissed: null });
  }

  /** A job object from a direct answer, such as cancel. Reports the end like a poll would. */
  takeJob(job: Job) {
    const prevJob = this.state.job;
    this.set({ job });
    if (prevJob?.state === "running" && prevJob.id === job.id && job.state !== "running") {
      this.finished.forEach((listener) => listener(job));
    }
  }

  get = () => this.state;

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  onFinished(listener: (job: Job) => void) {
    this.finished.add(listener);
    return () => {
      this.finished.delete(listener);
    };
  }

  onOnline(listener: Listener) {
    this.online.add(listener);
    return () => {
      this.online.delete(listener);
    };
  }

  set(patch: Partial<JobSnapshot>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener());
  }

  /** Fold one poll in. Returns true when the log must be read again from 0. */
  receive(data: JobPoll): boolean {
    const previous = this.state;
    const prevJob = previous.job;
    const job = data.job;

    const wasRunning = prevJob?.state === "running";
    const sameJob = Boolean(job && prevJob && job.id === prevJob.id);
    const endedJob = wasRunning && prevJob && (!sameJob || job?.state !== "running") ? (sameJob && job ? job : prevJob) : null;
    const watched = job?.state === "running" ? job.id : previous.watched;

    // The engine clears its log when a job starts, and its sequence numbers
    // restart with the engine. Either way the cursor goes back to 0 and the
    // log is read again from the top.
    const restarted = data.next < this.since;
    const newJob = Boolean(job && prevJob && job.id !== prevJob.id);
    let again = false;
    if ((restarted || newJob) && this.since !== 0) {
      this.since = 0;
      this.set({ job, log: [], truncated: false, offline: false, watched });
      again = true;
    } else {
      let log = newJob ? [] : previous.log;
      let truncated = (newJob ? false : previous.truncated) || data.truncated;
      if (data.events.length) {
        log = log.concat(data.events.map((event) => event.text));
        if (log.length > LOG_LIMIT) {
          log = log.slice(-LOG_LIMIT);
          truncated = true;
        }
      }
      this.since = data.next;
      this.set({ job, log, truncated, offline: false, watched });
    }

    if (previous.offline === true) this.online.forEach((listener) => listener());
    if (endedJob) this.finished.forEach((listener) => listener(endedJob));
    return again;
  }
}

type JobActions = {
  store: JobStore;
  /** A job endpoint answered 202 {job}: show it at once and poll fast. */
  start: (job: Job) => void;
  cancel: () => Promise<void>;
  dismiss: (jobId: string) => void;
  requestPlay: (projectId: string, name: string) => void;
  clearPlay: () => void;
  refresh: () => void;
};

const JobContext = createContext<JobActions | null>(null);

function useJobContext(): JobActions {
  const value = useContext(JobContext);
  if (!value) throw new Error("Job hooks need a JobProvider above them");
  return value;
}

export function JobProvider({ children }: { children: ReactNode }) {
  const [store] = useState(() => new JobStore());

  useEffect(() => {
    let timer: number | undefined;
    let stopped = false;
    let inFlight = false;

    const schedule = (ms: number) => {
      window.clearTimeout(timer);
      if (!stopped) timer = window.setTimeout(tick, ms);
    };

    async function tick() {
      if (stopped || document.hidden) return;
      if (inFlight) {
        schedule(FAST);
        return;
      }
      inFlight = true;
      let again = false;
      try {
        const data = await api<JobPoll>(`/api/job?since=${store.since}`);
        again = store.receive(data);
      } catch {
        store.set({ offline: true });
      } finally {
        inFlight = false;
      }
      const running = store.get().job?.state === "running";
      schedule(again ? 0 : running ? FAST : IDLE);
    }

    const onVisibility = () => {
      if (document.hidden) window.clearTimeout(timer);
      else schedule(0);
    };

    store.setPoke(() => schedule(0));
    document.addEventListener("visibilitychange", onVisibility);
    schedule(0);

    const mark = () => {
      document.documentElement.dataset.job = store.get().job?.state === "running" ? "running" : "idle";
    };
    const unsubscribe = store.subscribe(mark);

    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      unsubscribe();
    };
  }, [store]);

  const actions = useMemo<JobActions>(
    () => ({
      store,
      start(job) {
        store.startJob(job);
        store.poke();
      },
      async cancel() {
        // The engine waits up to 10 s for the job to stop, then answers with it.
        const result = await post<{ job: Job }>("/api/job/cancel", {});
        if (result?.job) store.takeJob(result.job);
        store.poke();
      },
      dismiss(jobId) {
        store.set({ dismissed: jobId });
      },
      requestPlay(projectId, name) {
        store.set({ play: { projectId, name, nonce: Date.now() } });
      },
      clearPlay() {
        store.set({ play: null });
      },
      refresh() {
        store.poke();
      },
    }),
    [store],
  );

  return <JobContext.Provider value={actions}>{children}</JobContext.Provider>;
}

/** Select a slice of the job state. Return primitives or stable references. */
export function useJob<T>(selector: (state: JobSnapshot) => T): T {
  const { store } = useJobContext();
  return useSyncExternalStore(
    store.subscribe,
    () => selector(store.get()),
    () => selector(initial),
  );
}

export function useJobActions() {
  return useJobContext();
}

/** Run `handler` whenever a job this tab saw running comes to an end. */
export function useJobFinished(handler: (job: Job) => void) {
  const { store } = useJobContext();
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => store.onFinished((job) => latest.current(job)), [store]);
}

/** Run `handler` when the engine answers again after being unreachable. */
export function useEngineOnline(handler: () => void) {
  const { store } = useJobContext();
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => store.onOnline(() => latest.current()), [store]);
}

/** What is running right now, as a stable string, or null. */
export function useRunning() {
  const kind = useJob((state) => (state.job?.state === "running" ? state.job.kind : null));
  const projectId = useJob((state) => (state.job?.state === "running" ? state.job.projectId : null));
  const projectName = useJob((state) => (state.job?.state === "running" ? state.job.projectName : null));
  return { kind, projectId, projectName };
}

/** The sentence that explains why another job cannot start yet. */
export function busyReason(running: { kind: string | null; projectName: string | null }): string | null {
  if (!running.kind) return null;
  const where = running.projectName ? ` for ${running.projectName}` : "";
  switch (running.kind) {
    case "render":
      return `A video is being built${where}. Wait for it or cancel it.`;
    case "transcribe":
      return `Narration is being transcribed${where}. Wait for it or cancel it.`;
    case "model":
      return "A speech model is downloading. Wait for it or cancel it.";
    default:
      return "The self-test is running. Wait for it or cancel it.";
  }
}
