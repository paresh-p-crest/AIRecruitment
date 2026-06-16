"use client";

import { DialogProvider } from "@/components/DialogProvider";
import { ThemeProvider } from "@/components/ThemeProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <DialogProvider>{children}</DialogProvider>
    </ThemeProvider>
  );
}
