import type { TFn, Vars } from "@/lib/i18n/types";

/**
 * Build a `t(key, vars?)` translator bound to a flat-or-nested dictionary.
 * Keys use dot notation (`common.save`). `{name}` placeholders interpolate
 * from `vars`. Missing keys fall back to the key string itself so the UI
 * never throws on an absent translation.
 */
export function makeT(dict: Record<string, unknown>): TFn {
  return (key: string, vars?: Vars): string => {
    const raw = resolve(dict, key);
    if (typeof raw !== "string") return key;
    if (!vars) return raw;
    return raw.replace(/\{(\w+)\}/g, (_, k: string) =>
      vars[k] !== undefined ? String(vars[k]) : `{${k}}`,
    );
  };
}

function resolve(obj: Record<string, unknown> | undefined, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => {
    if (o && typeof o === "object") {
      return (o as Record<string, unknown>)[k];
    }
    return undefined;
  }, obj);
}
