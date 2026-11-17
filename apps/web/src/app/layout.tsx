import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { siteUrl } from "@/lib/metadata";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "ClientExplain AI | Legal process workspace",
    template: "%s | ClientExplain AI",
  },
  description:
    "Organize legal process projects in a workspace designed for professional review.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
