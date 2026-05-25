import { type Choice, type ChoiceItem, choiceToDict, isSeparator, parseChoice, type RawChoice } from "../choice.js";
import { InvalidChoiceError, PromptAbortedError, ValidationError } from "../errors.js";
import { type ListItem, runListPrompt } from "../terminal.js";
import { ansi, getTheme, RESET } from "../theme.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface SelectConfig<V = unknown> extends BaseConfig<V> {
  choices: RawChoice<V>[];
  pageSize?: number;
  loop?: boolean;
}

export class SelectPrompt<V = unknown> extends BasePrompt<V> {
  private items: ChoiceItem<V>[];
  private choices: Choice<V>[];
  private pageSize: number;
  private loop: boolean;

  constructor(config: SelectConfig<V>) {
    super(config);
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
    return "select";
  }

  protected validateAnswer(value: unknown): V {
    for (const c of this.choices) {
      if (c.disabled) continue;
      if (value === c.value || value === c.name) return c.value;
    }
    const valid = this.choices.filter((c) => !c.disabled).map((c) => c.value);
    throw new ValidationError(`Invalid choice: ${JSON.stringify(value)}. Valid: ${JSON.stringify(valid)}`);
  }

  protected formatAnswer(value: V): string {
    for (const c of this.choices) {
      if (c.value === value) return c.short ?? c.name;
    }
    return String(value);
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

  protected async executeTerminal(): Promise<V> {
    const t = getTheme();
    const indices = this.selectableIndices();
    // indices is non-empty: constructor guarantees at least one selectable item
    let cursor = indices[0]!;

    if (this.defaultValue != null) {
      for (let i = 0; i < this.items.length; i++) {
        const item = this.items[i]!;
        if (!isSeparator(item) && !item.disabled && (item.value === this.defaultValue || item.name === String(this.defaultValue))) {
          cursor = i;
          break;
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
          result.push({ text: `  ${item.name}${reason} (disabled)`, style: ansi(t.muted) });
        } else if (i === cursor) {
          const desc = item.description ? ` - ${item.description}` : "";
          result.push({ text: `${t.symPointer} ${item.name}${desc}`, style: ansi(t.highlight) });
        } else {
          result.push({ text: `  ${item.name}`, style: "" });
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
        if (key === "enter") {
          const item = this.items[cursor]!;
          if (!isSeparator(item)) return { done: true, result: item.value };
          return { done: false };
        }
        if (key === "ctrl-c") return { done: true, result: null };
        return { done: false };
      },
    });

    if (raw === null) throw new PromptAbortedError("Prompt aborted by user");
    // raw comes from item.value which is already V, validate to satisfy the type system
    return this.validateAnswer(raw);
  }
}
