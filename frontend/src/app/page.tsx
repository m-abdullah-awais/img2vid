import type { Metadata } from "next";
import { ProjectsView } from "@/components/projects/ProjectsView";

// The root layout's title template does not reach a page in its own segment.
export const metadata: Metadata = {
  title: { absolute: "Projects | img2vid" },
};

// A static shell: the projects are fetched in the browser, from the local engine.
export default function Home() {
  return <ProjectsView />;
}
