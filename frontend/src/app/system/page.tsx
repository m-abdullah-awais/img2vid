import type { Metadata } from "next";
import { SystemView } from "@/components/system/SystemView";

export const metadata: Metadata = {
  title: "System",
};

export default function SystemPage() {
  return <SystemView />;
}
