import { type Choice, type ChoiceItem, choiceToDict, invalidChoiceMessage, isSeparator, parseChoice, type RawChoice, valuesMatch } from "../choice.js";
import { InvalidChoiceError, PromptAbortedError, ValidationError } from "../errors.js";
import { type ListItem, runListPrompt } from "../terminal.js";
import { ansi, getTheme, RESET } from "../theme.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface CheckboxConfig<V = unknown> extends BaseConfig<V[]> {
  choices: RawChoice<V>[];
  pageSize?: number;
  loop?: boolean;
  required?: boolean | string;
}

export class CheckboxPrompt<V = unknown> extends BasePrompt<V[]> {
  private items: ChoiceItem<V>[];
  private choices: Choice<V>[];
  private pageSize: number;
  private loop: boolean;
  private required: boolean | string;

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
    this.required = config.required ?? false;
  }

  get promptType(): string {
    return "checkbox";
  }

  protected validateAnswer(value: unknown): V[] {
    if (!Array.isArray(value)) throw new ValidationError(`Expected an array, got ${typeof value}`);
    const enabled = this.choices.filter((c) => !c.disabled);
    const validValues = enabled.map((c) => c.value);
    const result: V[] = [];
    for (const v of value) {
      // Type-aware value match OR exact string-name match; never string-coerce (R4).
      const match = enabled.find(
        (c) => valuesMatch(v, c.value) || (typeof v === "string" && v === c.name),
      );
      if (match) {
        result.push(match.value);
      } else {
        throw new ValidationError(invalidChoiceMessage(v, validValues));
      }
    }
    if (this.required && result.length === 0) {
      const msg = typeof this.required === "string" ? this.required : "At least one choice is required";
      throw new ValidationError(msg);
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
    // indices is non-empty: constructor guarantees at least one selectable item
    if (pos === -1) return indices[0]!;
    pos += direction;
    if (this.loop) {
      pos = ((pos % indices.length) + indices.length) % indices.length;
    } else {
      pos = Math.max(0, Math.min(pos, indices.length - 1));
    }
    // pos is clamped to [0, indices.length - 1]
    return indices[pos]!;
  }

  protected async executeTerminal(): Promise<V[]> {
    const t = getTheme();
    const indices = this.selectableIndices();
    // indices is non-empty: constructor guarantees at least one selectable item
    let cursor = indices[0]!;
    const checked = new Set<number>();
    const defaults = this.defaultValue ?? [];

    for (let i = 0; i < this.items.length; i++) {
      const item = this.items[i]!;
      if (!isSeparator(item) && !item.disabled) {
        // Check both value match and string name match for default pre-selection
        if (defaults.includes(item.value) || defaults.some((d) => d === item.name)) {
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
          else for (const i of indices) checked.add(i);
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
    // raw comes from item.value entries which are already V[], validate to satisfy the type system
    return this.validateAnswer(raw);
  }
}
