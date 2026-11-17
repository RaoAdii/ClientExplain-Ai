import { Settings } from "@/components/settings";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Settings",
  "View your account, project data and workspace configuration.",
  "/dashboard/settings",
  true,
);
export default function Page() {
  return <Settings />;
}
