import { NewProject } from "@/components/projects";
import { pageMetadata } from "@/lib/metadata";

export const metadata = pageMetadata("Create project", "Create a legal process project.", "/dashboard/projects/new", true);
export default function Page() { return <NewProject />; }
