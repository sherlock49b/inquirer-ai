import { type Choice, type ChoiceItem, type RawChoice, parseChoice, isSeparator, choiceToDict } from "../choice.js";
import { InvalidChoiceError, PromptAbortedError, ValidationError } from "../errors.js";
import { ansi, getTheme, RESET } from "../theme.js";
import { type ListItem, runListPrompt } from "../terminal.js";
import { BasePrompt, type BaseConfig } from "./base.js";

export interface CheckboxConfig<V = unknown> extends BaseConfig<V[]> {
  choices: RawChoice<V>[];
  pageSize?: number;
  loop?: boolean;
}

export class CheckboxPrompt<V = unknown> extends BasePrompt<V[]> {
  private items: ChoiceItem<V>[];
  private choices: Choice<V>[];
  private pageSize: number;
  private loop: boolean;

  constructor(config: CheckboxConfig<V>) {
    super({ ...config, default: config.default ?? [] });
    if (!config.choices.length) throw new InvalidChoiceError("choices cannot be empty");
    this.items = config.choices.map(parseChoice);
    this.choices = this.items.filter((c): c is Choice<V> => !isSeparator(c));
    if (!this.choices.some((c) => !c.disabled)) {
      throw new InvalidChoiceError("choices must contain at least one selectable item");
    }
    this.pageSize = config.pageSize ?? 10;
    this.loop = config.loop ?? true;
  }

  get promptType(): string {
    return "checkbox";
  }

  protected validateAnswer(value: unknown): V[] {
    if (!Array.isArray(value)) throw new ValidationError(`Expected an array, got ${typeof value}`);
    const enabled = this.choices.filter((c) => !c.disabled);
    const validValues = new Set(enabled.map((c) => c.value));
    const validNames = new Set(enabled.map((c) => c.name));
    const result: V[] = [];
    for (const v of value) {
      if (validValues.has(v as V)) {
        result.push(v as V);
      } else if (validNames.has(String(v))) {
        const match = enabled.find((c) => c.name === v);
        if (match) result.push(match.value);
      } else {
        throw new ValidationError(`Invalid choice: ${JSON.stringify(v)}. Valid: ${JSON.stringify([...validValues])}`);
      }
    }
    return result;
  }

  protected formatAnswer(value: V[]): string {
    const names = this.choices.filter((c) => value.includes(c.value)).map((c) => c.short ?? c.name);
    return names.length ? names.join(", ") : "none";
  }

  protected override toAgentDict(): Record<string, unknown> {
    return { ...super.toAgentDict(), choices: this.items.map(choiceToDict) };
  }

  private selectableIndices(): number[] {
    return this.items.reduce<number[]>((acc, item, i) => {
      if (!isSeparator(item) && !item.disabled) acc.push(i);
      return acc;
    }, []);
  }

  private moveCursor(current: number, direction: number): number {
    const indices = this.selectableIndices();
    let pos = indices.indexOf(current);
    if (pos === -1) return indices[0]!;
    pos += direction;
    if (this.loop) {
      pos = ((pos % indices.length) + indices.length) % indices.length;
    } else {
      pos = Math.max(0, Math.min(pos, indices.length - 1));
    }
    return indices[pos]!;
  }

  protected async executeTerminal(): Promise<V[]> {
    const t = getTheme();
    const indices = this.selectableIndices();
    let cursor = indices[0]!;
    const checked = new Set<number>();
    const defaults = this.defaultValue ?? [];

    for (let i = 0; i < this.items.length; i++) {
      const item = this.items[i]!;
      if (!isSeparator(item) && !item.disabled) {
        if (defaults.includes(item.value) || defaults.includes(item.name as V)) {
          checked.add(i);
        }
      }
    }

    const getItems = (): ListItem[] => {
      const total = this.items.length;
      const ps = Math.min(this.pageSize, total);
      const start = Math.max(0, Math.min(cursor - Math.floor(ps / 2), total - ps));
      const end = start + ps;
      const result: ListItem[] = [];

      if (start > 0) result.push({ text: `  ${ansi(t.muted)}(more above)${RESET}`, style: "" });

      for (let i = start; i < end; i++) {
        const item = this.items[i]!;
        if (isSeparator(item)) {
          result.push({ text: `  ${item.text}`, style: ansi(t.muted) });
        } else if (item.disabled) {
          const reason = typeof item.disabled === "string" ? ` (${item.disabled})` : "";
          result.push({ text: `  ${t.symUnchecked} ${item.name}${reason} (disabled)`, style: ansi(t.muted) });
        } else {
          const arrow = i === cursor ? t.symPointer : " ";
          const mark = checked.has(i) ? t.symChecked : t.symUnchecked;
          let style = "";
          if (i === cursor) style = ansi(t.highlight);
          else if (checked.has(i)) style = ansi(t.selected);
          result.push({ text: `${arrow} ${mark} ${item.name}`, style });
        }
      }

      if (end < total) result.push({ text: `  ${ansi(t.muted)}(more below)${RESET}`, style: "" });
      return result;
    };

    const raw = await runListPrompt({
      message: this.message,
      getItems,
      onKey: (key) => {
        if (key === "up" || key === "k") {
          cursor = this.moveCursor(cursor, -1);
          return { done: false };
        }
        if (key === "down" || key === "j") {
          cursor = this.moveCursor(cursor, 1);
          return { done: false };
        }
        if (key === "space") {
          if (checked.has(cursor)) checked.delete(cursor);
          else checked.add(cursor);
          return { done: false };
        }
        if (key === "a") {
          if (checked.size === indices.length) checked.clear();
          else indices.forEach((i) => checked.add(i));
          return { done: false };
        }
        if (key === "enter") {
          const result: V[] = [];
          for (const i of [...checked].sort((a, b) => a - b)) {
            const item = this.items[i]!;
            if (!isSeparator(item)) result.push(item.value);
          }
          return { done: true, result };
        }
        if (key === "ctrl-c") return { done: true, result: null };
        return { done: false };
      },
    });

    if (raw === null) throw new PromptAbortedError("Prompt aborted by user");
    return raw as V[];
  }
}
