"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

type DialogVariant = "default" | "danger" | "success" | "error" | "warning";

interface AlertOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  variant?: DialogVariant;
}

interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: DialogVariant;
}

interface DialogState {
  type: "alert" | "confirm";
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  variant: DialogVariant;
  resolve: (value: boolean) => void;
}

interface DialogContextValue {
  alert: (options: AlertOptions) => Promise<void>;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const DialogContext = createContext<DialogContextValue | null>(null);

const variantStyles: Record<
  DialogVariant,
  { icon: React.ElementType; iconClass: string; ring: string }
> = {
  default: {
    icon: Info,
    iconClass: "text-brand-400 bg-brand-500/15 ring-brand-500/30",
    ring: "ring-brand-500/20",
  },
  danger: {
    icon: AlertTriangle,
    iconClass: "text-red-400 bg-red-500/15 ring-red-500/30",
    ring: "ring-red-500/20",
  },
  success: {
    icon: CheckCircle2,
    iconClass: "text-emerald-400 bg-emerald-500/15 ring-emerald-500/30",
    ring: "ring-emerald-500/20",
  },
  error: {
    icon: AlertCircle,
    iconClass: "text-red-400 bg-red-500/15 ring-red-500/30",
    ring: "ring-red-500/20",
  },
  warning: {
    icon: AlertTriangle,
    iconClass: "text-amber-400 bg-amber-500/15 ring-amber-500/30",
    ring: "ring-amber-500/20",
  },
};

export function DialogProvider({ children }: { children: React.ReactNode }) {
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  const close = useCallback((result: boolean) => {
    setDialog((current) => {
      current?.resolve(result);
      return null;
    });
  }, []);

  const alert = useCallback(
    (options: AlertOptions) =>
      new Promise<void>((resolve) => {
        setDialog({
          type: "alert",
          title: options.title,
          message: options.message,
          confirmLabel: options.confirmLabel ?? "OK",
          variant: options.variant ?? "default",
          resolve: () => resolve(),
        });
      }),
    []
  );

  const confirm = useCallback(
    (options: ConfirmOptions) =>
      new Promise<boolean>((resolve) => {
        setDialog({
          type: "confirm",
          title: options.title,
          message: options.message,
          confirmLabel: options.confirmLabel ?? "Confirm",
          cancelLabel: options.cancelLabel ?? "Cancel",
          variant: options.variant ?? "default",
          resolve,
        });
      }),
    []
  );

  useEffect(() => {
    if (!dialog) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        close(dialog.type === "confirm" ? false : true);
      }
    };

    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    confirmRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [dialog, close]);

  const style = dialog ? variantStyles[dialog.variant] : null;
  const Icon = style?.icon;

  return (
    <DialogContext.Provider value={{ alert, confirm }}>
      {children}

      {dialog && style && Icon && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fade-in"
            onClick={() => close(dialog.type === "confirm" ? false : true)}
            aria-hidden
          />

          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            aria-describedby="dialog-message"
            className={cn(
              "relative w-full max-w-md animate-slide-up rounded-2xl border border-white/10 bg-slate-900 p-6 shadow-2xl ring-1",
              style.ring
            )}
          >
            <button
              type="button"
              onClick={() => close(dialog.type === "confirm" ? false : true)}
              className="absolute right-4 top-4 rounded-lg p-1 text-slate-500 transition hover:bg-white/10 hover:text-white"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="flex gap-4">
              <div
                className={cn(
                  "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1",
                  style.iconClass
                )}
              >
                <Icon className="h-5 w-5" />
              </div>

              <div className="min-w-0 flex-1 pr-6">
                <h2
                  id="dialog-title"
                  className="font-display text-lg font-semibold text-white"
                >
                  {dialog.title}
                </h2>
                <p
                  id="dialog-message"
                  className="mt-2 text-sm leading-relaxed text-slate-400"
                >
                  {dialog.message}
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              {dialog.type === "confirm" && (
                <button
                  type="button"
                  onClick={() => close(false)}
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-300 transition hover:bg-white/10 hover:text-white"
                >
                  {dialog.cancelLabel}
                </button>
              )}
              <button
                ref={confirmRef}
                type="button"
                onClick={() => close(true)}
                className={cn(
                  "rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition",
                  dialog.variant === "danger"
                    ? "bg-red-500 hover:bg-red-400"
                    : dialog.variant === "error"
                      ? "bg-red-500 hover:bg-red-400"
                      : "bg-brand-500 hover:bg-brand-400"
                )}
              >
                {dialog.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}

export function useDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) {
    throw new Error("useDialog must be used within DialogProvider");
  }
  return ctx;
}
