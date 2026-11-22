import { ProjectWorkspace } from "@/components/project-workspace";
import { pageMetadata } from "@/lib/metadata";
import { notFound } from "next/navigation";
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return pageMetadata(
    "Project details",
    "Review and edit your legal process project context.",
    `/dashboard/projects/${id}`,
    true,
  );
}
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  return <ProjectWorkspace id={id} />;
}
