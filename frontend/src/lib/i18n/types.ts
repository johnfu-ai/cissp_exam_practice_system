export type Locale = "en" | "zh";

export type Vars = Record<string, string | number>;

export type TFn = (key: string, vars?: Vars) => string;
