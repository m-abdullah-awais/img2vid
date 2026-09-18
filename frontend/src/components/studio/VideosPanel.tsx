"use client";

import { Download, Play, Square, Trash2 } from "lucide-react";
import { memo, useEffect, useRef, useState } from "react";
import { apiUrl } from "@/lib/api";
import { bytes, clock, relative, stamp } from "@/lib/format";
import { useNow } from "@/lib/hooks/useNow";
import type { Video } from "@/lib/types";
import { useJobActions } from "../job/JobProvider";
import { Button, buttonClass, IconButton } from "../ui/Button";

type Props = {
  projectId: string;
  videos: Video[];
  onRemove: (name: string) => Promise<void>;
  onBuild: () => void;
  busy: string | null;
  /** Nothing stops a build right now, so the empty state can offer one. */
  ready: boolean;
};

/** Every video built for this project, newest first, each playable in place. */
export const VideosPanel = memo(function VideosPanel({ projectId, videos, onRemove, onBuild, busy, ready }: Props) {
  const [playing, setPlaying] = useState<string | null>(null);
  const { store, clearPlay } = useJobActions();
  const section = useRef<HTMLElement>(null);
  const now = useNow();

  // "Play" in the job dock asks for a video; answer it once this project is on screen.
  useEffect(() => {
    const take = () => {
      const request = store.get().play;
      if (!request || request.projectId !== projectId) return;
      clearPlay();
      setPlaying(request.name);
      window.setTimeout(() => section.current?.scrollIntoView({ block: "start" }), 50);
    };
    const first = window.setTimeout(take, 0);
    const unsubscribe = store.subscribe(take);
    return () => {
      window.clearTimeout(first);
      unsubscribe();
    };
  }, [store, clearPlay, projectId]);

  async function remove(name: string) {
    if (playing === name) {
      // Let the player let go of the file first, or Windows refuses to move it.
      setPlaying(null);
      await new Promise((resolve) => window.setTimeout(resolve, 200));
    }
    await onRemove(name);
  }

  return (
    <section ref={section} id="videos" aria-labelledby="videos-title" className="flex scroll-mt-6 flex-col gap-3">
      <h2 id="videos-title" className="heading text-2xl">
        Videos
      </h2>
      {videos.length === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-[var(--radius-control)] border border-dashed border-hairline px-5 py-6">
          <p className="max-w-[62ch] text-sm text-muted">
            No video yet. Build video when the storyboard is ready, and it appears here to play and
            download. Every build is kept, named by the time it was made.
          </p>
          {ready ? (
            <Button size="sm" variant="secondary" onClick={onBuild} disabled={Boolean(busy)} title={busy ?? undefined}>
              Build video
            </Button>
          ) : null}
        </div>
      ) : (
        <ul className="divide-y divide-hairline border-y border-hairline">
          {videos.map((video, index) => {
            const open = playing === video.name;
            return (
              <li key={video.name} className="flex flex-col gap-2 py-3">
                <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                  <div className="min-w-0 flex-1">
                    <p className="timecode text-base break-all">{video.name}</p>
                    <p className="timecode flex flex-wrap gap-x-4 text-sm text-muted">
                      <span>{clock(video.seconds)}</span>
                      <span>{bytes(video.bytes)}</span>
                      <span title={stamp(video.createdAt)}>Built {now ? relative(video.createdAt, now) : stamp(video.createdAt)}</span>
                      {index === 0 ? <span className="text-text">Newest</span> : null}
                    </p>
                    {video.outdated ? (
                      <p className="mt-0.5 flex items-center gap-1.5 text-sm text-missing">
                        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-missing" />
                        Built before the latest changes to the narration, transcript or images
                      </p>
                    ) : null}
                    {video.summary ? <p className="mt-0.5 text-sm text-muted">{video.summary}</p> : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant={open ? "secondary" : "primary"}
                      aria-expanded={open}
                      onClick={() => setPlaying(open ? null : video.name)}
                    >
                      {open ? <Square size={14} aria-hidden /> : <Play size={15} aria-hidden />}
                      {open ? "Close player" : "Play"}
                    </Button>
                    <a className={buttonClass("secondary", "sm")} href={apiUrl(video.download)}>
                      <Download size={15} aria-hidden />
                      Download
                    </a>
                    <IconButton label={`Remove ${video.name}`} onClick={() => void remove(video.name)}>
                      <Trash2 size={16} aria-hidden />
                    </IconButton>
                  </div>
                </div>
                {open ? (
                  <video
                    key={video.url}
                    src={apiUrl(video.url)}
                    controls
                    autoPlay
                    preload="metadata"
                    className="aspect-video w-full max-w-[960px] rounded-[var(--radius-frame)] border border-hairline bg-[#000]"
                  >
                    Your browser cannot play this video here. Download it instead.
                  </video>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
});
