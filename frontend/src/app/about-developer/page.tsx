import { ExternalLink } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About the developer",
};

const links = [
  { label: "Website", href: "https://www.abdullahawais.com", text: "www.abdullahawais.com" },
  { label: "Email", href: "mailto:contact@abdullahawais.com", text: "contact@abdullahawais.com" },
  {
    label: "LinkedIn",
    href: "https://www.linkedin.com/in/m-abdullah-awais-programmer",
    text: "in/m-abdullah-awais-programmer",
  },
  { label: "GitHub", href: "https://github.com/m-abdullah-awais", text: "m-abdullah-awais" },
  { label: "YouTube", href: "https://www.youtube.com/@m_abdullah_awais", text: "@m_abdullah_awais" },
  { label: "Instagram", href: "https://www.instagram.com/m_abdullah_awais", text: "m_abdullah_awais" },
];

const stack = [
  {
    part: "This app",
    what: "Next.js and React. It runs in your browser and talks only to the engine on this computer.",
  },
  {
    part: "The engine",
    what: "A small API written in Python with the standard library alone, so there is nothing to install from the internet.",
  },
  {
    part: "Video",
    what: "ffmpeg does every frame. Each image is held from its line's timestamp until the next one, counted in whole frames, so the video runs exactly as long as the narration.",
  },
  {
    part: "Speech",
    what: "faster-whisper, offline, on the processor. The narration never leaves this computer.",
  },
];

/** A monogram instead of a photo, so this page makes no request outside the app. */
function Monogram() {
  return (
    <div
      aria-hidden
      className="flex aspect-square w-36 flex-col justify-between rounded-[var(--radius-control)] border border-hairline bg-panel p-4 sm:w-44"
    >
      <span className="heading text-[4.5rem] leading-[0.85] tracking-[-0.01em] sm:text-[5.5rem]">MAA</span>
      <span className="flex h-2 w-full gap-px">
        <span className="flex-[3] bg-text" />
        <span className="flex-[2] bg-ready" />
        <span className="flex-[1] hatch" />
        <span className="flex-[4] bg-text" />
        <span className="flex-[2] bg-muted" />
      </span>
    </div>
  );
}

export default function AboutDeveloper() {
  return (
    <div className="flex max-w-[1040px] flex-col gap-14 pt-4">
      <section aria-labelledby="developer-name" className="grid gap-8 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-end">
        <Monogram />
        <div className="flex flex-col gap-1">
          <h1 id="developer-name" className="heading text-3xl sm:text-[3rem] sm:leading-[1.05]">
            Muhammad Abdullah Awais
          </h1>
          <p className="text-lg text-muted">Full Stack Developer</p>
        </div>
      </section>

      <section aria-labelledby="contact-title" className="grid gap-4 sm:grid-cols-[11rem_minmax(0,1fr)]">
        <h2 id="contact-title" className="heading text-2xl">
          Contact
        </h2>
        <dl className="divide-y divide-hairline border-y border-hairline">
          {links.map((link) => {
            const external = link.href.startsWith("http");
            return (
              <div key={link.label} className="grid gap-0.5 py-3 sm:grid-cols-[6.5rem_minmax(0,1fr)] sm:items-baseline sm:gap-4">
                <dt className="text-sm text-muted">{link.label}</dt>
                <dd className="min-w-0">
                  <a
                    href={link.href}
                    {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                    className="inline-flex max-w-full items-center gap-1.5 [overflow-wrap:anywhere] underline decoration-hairline underline-offset-4 hover:decoration-text"
                  >
                    {link.text}
                    {external ? (
                      <>
                        <ExternalLink size={14} aria-hidden className="shrink-0 text-muted" />
                        <span className="sr-only">(opens in a new tab)</span>
                      </>
                    ) : null}
                  </a>
                </dd>
              </div>
            );
          })}
        </dl>
      </section>

      <section aria-labelledby="app-title" className="grid gap-4 sm:grid-cols-[11rem_minmax(0,1fr)]">
        <h2 id="app-title" className="heading text-2xl">
          About img2vid
        </h2>
        <div className="flex flex-col gap-6">
          <p className="max-w-[64ch] text-base">
            img2vid turns a narration and one image per transcript line into a finished MP4. It was made for
            explainer videos, where every sentence has its picture. Each image goes on the line its
            filename number names, so a missing one leaves a gap instead of shifting everything after it,
            and speed comes first at every step.
          </p>
          <dl className="divide-y divide-hairline border-y border-hairline">
            {stack.map((item) => (
              <div key={item.part} className="grid gap-1 py-3 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-4">
                <dt className="font-semibold">{item.part}</dt>
                <dd className="max-w-[64ch] text-sm text-muted">{item.what}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </div>
  );
}
