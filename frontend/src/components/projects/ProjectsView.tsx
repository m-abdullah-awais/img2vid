"use client";

import { Plus } from "lucide-react";
import { useCallback, useState } from "react";
import { del, patch, post, toApiError } from "@/lib/api";
import { useNow } from "@/lib/hooks/useNow";
import { useProjects } from "@/lib/hooks/useProjects";
import type { ProjectEnvelope, ProjectSummary, RestoreResult } from "@/lib/types";
import { useEngineOnline, useJobFinished } from "../job/JobProvider";
import { Button } from "../ui/Button";
import { EngineDown } from "../ui/EngineDown";
import { useToast } from "../ui/Toast";
import { NewProjectDialog } from "./NewProjectDialog";
import { ProjectRow } from "./ProjectRow";

export function ProjectsView() {
  const { projects, error, loading, refetch, update } = useProjects();
  const { toast } = useToast();
  const now = useNow();
  const [creating, setCreating] = useState(false);

  useJobFinished(() => void refetch());
  useEngineOnline(() => void refetch());

  const rename = useCallback(
    async (project: ProjectSummary, name: string) => {
      try {
        const result = await patch<ProjectEnvelope>(`/api/projects/${encodeURIComponent(project.id)}`, { name });
        update((list) =>
          list.map((item) =>
            item.id === project.id
              ? { ...item, name: result.project?.name ?? name, updatedAt: result.project?.updatedAt ?? item.updatedAt }
              : item,
          ),
        );
        return true;
      } catch (failure) {
        toast({ tone: "error", message: "Not renamed", detail: toApiError(failure).message });
        return false;
      }
    },
    [toast, update],
  );

  const remove = useCallback(
    async (project: ProjectSummary) => {
      try {
        const { trashId } = await del<{ trashId: string }>(`/api/projects/${encodeURIComponent(project.id)}`);
        update((list) => list.filter((item) => item.id !== project.id));
        toast({
          tone: "info",
          message: `Deleted ${project.name}`,
          detail: "It stays in the trash for 7 days.",
          action: {
            label: "Undo",
            run: async () => {
              try {
                await post<RestoreResult>(`/api/trash/${encodeURIComponent(trashId)}/restore`);
                toast({ tone: "done", message: `Restored ${project.name}` });
              } catch (failure) {
                toast({ tone: "error", message: "Not restored", detail: toApiError(failure).message });
              }
              await refetch();
            },
          },
        });
      } catch (failure) {
        toast({ tone: "error", message: `${project.name} was not deleted`, detail: toApiError(failure).message });
      }
    },
    [refetch, toast, update],
  );

  if (error && error.code === "unreachable" && !projects) {
    return <EngineDown onRetry={refetch} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="heading text-3xl">Projects</h1>
          {projects && projects.length ? (
            <p className="text-sm text-muted">
              {projects.length === 1 ? "1 project" : `${projects.length} projects`}, most recently changed first
            </p>
          ) : null}
        </div>
        {projects && projects.length ? (
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden />
            New project
          </Button>
        ) : null}
      </div>

      {error && error.code !== "unreachable" ? (
        <div role="alert" className="flex items-start gap-3 border-l-2 border-build bg-panel px-4 py-3 text-sm">
          <div className="flex-1">
            <p className="font-medium">Projects could not be loaded</p>
            <p className="text-muted">{error.message}</p>
          </div>
          <Button size="sm" onClick={() => void refetch()}>
            Retry
          </Button>
        </div>
      ) : null}

      {loading && !projects ? (
        <p className="py-10 text-sm text-muted" aria-live="polite">
          Loading projects
        </p>
      ) : null}

      {projects && projects.length === 0 ? <FirstRun onCreate={() => setCreating(true)} /> : null}

      {projects && projects.length ? (
        <ul className="divide-y divide-hairline border-y border-hairline">
          {projects.map((project, index) => (
            <ProjectRow
              key={project.id}
              project={project}
              now={now}
              eager={index < 6}
              onRename={rename}
              onDelete={remove}
            />
          ))}
        </ul>
      ) : null}

      {creating ? <NewProjectDialog onClose={() => setCreating(false)} /> : null}
    </div>
  );
}

function FirstRun({ onCreate }: { onCreate: () => void }) {
  const steps = [
    {
      title: "Create a project",
      body: "One project per video. Name it after the video.",
    },
    {
      title: "Upload the narration",
      body: "One audio file, or several that are joined in name order.",
    },
    {
      title: "Transcribe it",
      body: "Every transcript line becomes one image in the video.",
    },
    {
      title: "Add one image per line, then build the video",
      body: "An image named 012 goes on line 12, so a missing one never shifts the rest.",
    },
  ];
  return (
    <section aria-labelledby="first-run" className="grid gap-10 border-t border-hairline pt-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="flex flex-col items-start gap-4">
        <h2 id="first-run" className="heading text-3xl">
          Start your first video
        </h2>
        <p className="max-w-[46ch] text-muted">
          img2vid turns your narration and one image per transcript line into an MP4. Everything
          stays on this computer.
        </p>
        <Button variant="primary" onClick={onCreate}>
          <Plus size={16} aria-hidden />
          New project
        </Button>
      </div>
      <ol className="flex flex-col">
        {steps.map((step, index) => (
          <li key={step.title} className="grid grid-cols-[2.5rem_1fr] gap-x-3 border-b border-hairline py-3 first:pt-0">
            <span className="timecode text-xl text-muted">{index + 1}</span>
            <div>
              <p className="font-semibold">{step.title}</p>
              <p className="text-sm text-muted">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
