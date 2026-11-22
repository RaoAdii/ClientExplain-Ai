import { Projects } from "@/components/projects";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Projects",
  "Search, filter, create and manage your legal process projects.",
  "/dashboard/projects",
  true,
);
export default function Page() {
  return <Projects />;
}
