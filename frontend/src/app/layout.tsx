import type { Metadata, Viewport } from "next";
import { Barlow, Barlow_Condensed, Barlow_Semi_Condensed } from "next/font/google";
import { JobDock } from "@/components/job/JobDock";
import { JobProvider } from "@/components/job/JobProvider";
import { SiteHeader } from "@/components/SiteHeader";
import { ToastProvider } from "@/components/ui/Toast";
import "./globals.css";

// One family at three widths. Downloaded at build time and served from this
// app, so the browser never asks Google for anything.
const barlow = Barlow({
  variable: "--font-barlow",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
});

const barlowSemi = Barlow_Semi_Condensed({
  variable: "--font-barlow-semi",
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500"],
});

const barlowCondensed = Barlow_Condensed({
  variable: "--font-barlow-cond",
  subsets: ["latin", "latin-ext"],
  weight: ["600"],
});

export const metadata: Metadata = {
  title: {
    template: "%s | img2vid",
    default: "img2vid",
  },
  description: "Turn narration and one image per line into a finished video, on this computer.",
};

export const viewport: Viewport = {
  themeColor: "#1B1F24",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      data-job="idle"
      className={`${barlow.variable} ${barlowSemi.variable} ${barlowCondensed.variable}`}
    >
      <body className="min-h-dvh bg-graphite font-sans text-text">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-[var(--radius-control)] focus:bg-text focus:px-3 focus:py-2 focus:text-graphite"
        >
          Skip to content
        </a>
        <ToastProvider>
          <JobProvider>
            <SiteHeader />
            <main
              id="main"
              className="mx-auto w-full max-w-[1400px] px-4 pt-6 sm:px-6 lg:px-8"
              style={{ paddingBottom: "calc(var(--dock-h, 0px) + 4rem)" }}
            >
              {children}
            </main>
            <JobDock />
          </JobProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
