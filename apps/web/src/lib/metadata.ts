import type { Metadata } from "next";
export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
export function pageMetadata(
  title: string,
  description: string,
  path: string,
  privatePage = false,
): Metadata {
  return {
    title: { absolute: `${title} | ClientExplain AI` },
    description,
    alternates: { canonical: path },
    ...(privatePage ? { robots: { index: false, follow: false } } : {}),
  };
}
