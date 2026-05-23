export interface Choice<V = unknown> {
  name: string;
  value: V;
  disabled?: boolean | string;
  short?: string;
  description?: string;
}

export interface Separator {
  type: "separator";
  text: string;
}

export type ChoiceItem<V = unknown> = Choice<V> | Separator;
export type RawChoice<V = unknown> = string | Choice<V> | Separator;

export function isSeparator(item: ChoiceItem): item is Separator {
  return "type" in item && item.type === "separator";
}

export function createSeparator(text = "────────"): Separator {
  return { type: "separator", text };
}

export function parseChoice<V = unknown>(raw: RawChoice<V>): ChoiceItem<V> {
  if (typeof raw === "string") {
    return { name: raw, value: raw as V };
  }
  if ("type" in raw && raw.type === "separator") {
    return raw;
  }
  return raw;
}

export function choiceToDict(item: ChoiceItem): Record<string, unknown> {
  if (isSeparator(item)) {
    return { type: "separator", text: item.text };
  }
  const d: Record<string, unknown> = { name: item.name, value: item.value };
  if (item.disabled) d.disabled = item.disabled;
  if (item.short != null) d.short = item.short;
  if (item.description != null) d.description = item.description;
  return d;
}
