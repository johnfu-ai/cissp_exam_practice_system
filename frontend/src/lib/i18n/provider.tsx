"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { en } from "@/locales/en";
import { zh } from "@/locales/zh";
import { makeT } from "@/locales/t";
import { useAuthStore } from "@/lib/auth-store";
import { writeUiLangCookie } from "./cookie";
import type { Locale, TFn } from "./types";

const DICTS: Record<Locale, Record<string, unknown>> = { en, zh };

interface I18nCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: TFn;
}

const Ctx = createContext<I18nCtx | null>(null);

/**
 * Provides the active UI locale and a `t()` translator to the whole app.
 *
 * Locale resolution order:
 *   1. `initialLocale` (server-read `ui_lang` cookie) — prevents first-paint
 *      flash and hydration mismatch.
 *   2. When the auth store hydrates a user (login / reload), snap the locale
 *      to that user's persisted `interface_language` once per user id, so the
 *      server preference wins over a stale cookie (e.g. cross-device).
 *   3. The Settings page calls `setLocale` directly on user action.
 */
export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const user = useAuthStore((s) => s.user);
  const syncedUserId = useRef<string | null>(null);

  // Sync to the persisted server preference once per authenticated user.
  useEffect(() => {
    if (!user) return;
    if (syncedUserId.current === user.id) return;
    syncedUserId.current = user.id;
    const pref = user.interface_language;
    if (pref === "en" || pref === "zh") {
      setLocaleState(pref);
      writeUiLangCookie(pref);
    }
  }, [user]);

  const value = useMemo<I18nCtx>(() => {
    const setLocale = (l: Locale) => {
      setLocaleState(l);
      writeUiLangCookie(l);
    };
    return { locale, setLocale, t: makeT(DICTS[locale]) };
  }, [locale]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18nCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

export function useT(): TFn {
  return useI18n().t;
}
