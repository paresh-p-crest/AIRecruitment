import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "SliceHRMS AI Recruitment platform overview, features, technology stack, and live demo links.",
};

export default function DocumentationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
