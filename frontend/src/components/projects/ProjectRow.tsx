"use client";

import { Film, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { memo, useState } from "react";
import { clock, plural, relative, stamp } from "@/lib/format";
import { toneText } from "@/lib/tone";
import type { ProjectSummary } from "@/lib/types";
import { IconButton } from "../ui/Button";
import { Thumb } from "../ui/Thumb";

type Props = {
  project: ProjectSummary;
  now: number;
  eager: boolean;
  onRename: (project: ProjectSummary, name: string) => Promise<boolean>;
  onDelete: (project: ProjectSummary) => void;
};

/** One project in the bin: its cover, its name, where it stands, and when it last changed. */
export const ProjectRow = memo(function ProjectRow({ project, now, eager, onRename, onDelete }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(project.name);
  const [saving, setSaving] = useState(false);

  async function save() {
    const clean = draft.trim();
    if (!clean || clean === project.name) {
      setEditing(false);
      setDraft(project.name);
      return;
    }
    setSaving(true);
    const ok = await onRename(project, clean);
    setSaving(false);
    if (ok) setEditing(false);
  }

  const counts = project.counts;

  return (
    <li className="relative grid grid-cols-[96px_1fr] items-center gap-x-4 gap-y-1 py-3 sm:grid-cols-[128px_minmax(0,1fr)_auto] sm:gap-x-6">
      <div className="row-span-2 aspect-video w-full overflow-hidden rounded-[var(--radius-frame)] border border-hairline sm:row-span-1">
        {project.cover ? (
          <Thumb src={project.cover} alt="" eager={eager} className="h-full w-full" />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-panel text-muted">
            <Film size={18} aria-hidden />
          </div>
        )}
      </div>

      <div className="min-w-0">
        {editing ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
            className="flex items-center gap-2"
          >
            <label className="sr-only" htmlFor={`rename-${project.id}`}>
              New name for {project.name}
            </label>
            <input
              id={`rename-${project.id}`}
              value={draft}
              autoFocus
              disabled={saving}
              maxLength={120}
              onChange={(event) => setDraft(event.target.value)}
              onBlur={() => void save()}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.preventDefault();
                  setDraft(project.name);
                  setEditing(false);
                }
              }}
              className="relative z-10 h-9 w-full max-w-[420px] rounded-[var(--radius-control)] border border-text bg-graphite px-2 text-lg font-semibold"
            />
          </form>
        ) : (
          <Link
            href={`/projects/${project.id}`}
            className="text-lg font-semibold break-words after:absolute after:inset-0 after:content-[''] hover:underline hover:decoration-hairline hover:underline-offset-4"
          >
            {project.name}
          </Link>
        )}
        <p className={`text-sm ${toneText[project.status.tone]}`}>{project.status.text}</p>
        <p className="timecode mt-1 flex flex-wrap gap-x-4 text-sm text-muted">
          {counts.lines ? <span>{plural(counts.lines, "line")}</span> : null}
          {counts.images ? <span>{plural(counts.images, "image")}</span> : null}
          {counts.videos ? <span>{plural(counts.videos, "video")}</span> : null}
          {project.seconds ? <span>{clock(project.seconds)} narration</span> : null}
          <span title={stamp(project.updatedAt)}>Changed {now ? relative(project.updatedAt, now) : stamp(project.updatedAt)}</span>
        </p>
      </div>

      <div className="relative z-10 col-start-2 flex items-center gap-1 sm:col-start-3">
        <IconButton
          label={`Rename ${project.name}`}
          onClick={() => {
            setDraft(project.name);
            setEditing(true);
          }}
          disabled={editing}
        >
          <Pencil size={16} aria-hidden />
        </IconButton>
        <IconButton label={`Delete ${project.name}`} onClick={() => onDelete(project)}>
          <Trash2 size={16} aria-hidden />
        </IconButton>
      </div>
    </li>
  );
});
