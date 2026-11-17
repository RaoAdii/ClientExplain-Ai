import { Projects } from "@/components/projects";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Workspace overview",
  "Your legal process workspace and saved projects.",
  "/dashboard",
  true,
);
export default function Dashboard() {
  return <Projects overview />;
}
