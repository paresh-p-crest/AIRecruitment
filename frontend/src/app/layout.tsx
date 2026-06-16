import type { Metadata } from "next";
import { DM_Sans, Outfit } from "next/font/google";
import { Providers } from "@/components/Providers";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

export const metadata: Metadata = {
  title: {
    default: "SliceHRMS — AI Recruitment",
    template: "%s · SliceHRMS",
  },
  description:
    "Upload resumes, search candidates with AI, and run hybrid job matching with SliceHRMS.",
  applicationName: "SliceHRMS",
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/apple-icon.svg", type: "image/svg+xml" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("slicehrms-theme");var theme=t==="light"?"light":"dark";document.documentElement.setAttribute("data-theme",theme);document.documentElement.style.colorScheme=theme;}catch(e){}})();`,
          }}
        />
      </head>
      <body className={`${dmSans.variable} ${outfit.variable} font-sans`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
