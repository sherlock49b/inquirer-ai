import { type Choice, choiceToDict, invalidChoiceMessage, isSeparator, parseChoice, type RawChoice, valuesMatch } from "../choice.js";
import { InvalidChoiceError, ValidationError } from "../errors.js";
import { formatError, formatQuestion, readLine } from "../terminal.js";
import { type BaseConfig, BasePrompt } from "./base.js";

export interface RawlistConfig extends BaseConfig<unknown> {
  choices: RawChoice[];
}

export class RawlistPrompt extends BasePrompt<unknown> {
  // Selectable list = choices excluding separators AND disabled. Index range
  // and matching operate over this list only (R5).
  private choices: Choice[];

  constructor(config: RawlistConfig) {
    super(config);
    if (!config.choices.length) throw new InvalidChoiceError("choices cannot be empty");
    this.choices = config.choices
      .map(parseChoice)
      .filter((c): c is Choice => !isSeparator(c) && !c.disabled);
    if (!this.choices.length) throw new InvalidChoiceError("choices cannot be empty");
  }

  get promptType(): string {
    return "rawlist";
  }

  protected validateAnswer(value: unknown): unknown {
    const validValues = this.choices.map((c) => c.value);
    // A numeric answer is a 1-based index over the selectable list. A
    // non-integer index (e.g. 1.5) is rejected, not truncated (R5).
    if (typeof value === "number") {
      if (!Number.isInteger(value)) {
        throw new ValidationError(invalidChoiceMessage(value, validValues));
      }
      if (value >= 1 && value <= this.choices.length) {
        return this.choices[value - 1]?.value;
      }
      throw new ValidationError(invalidChoiceMessage(value, validValues));
    }
    for (const c of this.choices) {
      if (valuesMatch(value, c.value) || (typeof value === "string" && value === c.name)) {
        return c.value;
      }
    }
    throw new ValidationError(invalidChoiceMessage(value, validValues));
  }

  protected formatAnswer(value: unknown): string {
    for (const c of this.choices) {
      if (c.value === value) return c.short ?? c.name;
    }
    return String(value);
  }

  protected override toAgentDict(): Record<string, unknown> {
    return { ...super.toAgentDict(), choices: this.choices.map(choiceToDict) };
  }

  protected async executeTerminal(): Promise<unknown> {
    for (let i = 0; i < this.choices.length; i++) {
      process.stderr.write(`  ${i + 1}) ${this.choices[i]?.name}\n`);
    }
    const prompt = formatQuestion(this.message);
    while (true) {
      const raw = await readLine(prompt);
      const idx = parseInt(raw, 10);
      if (!Number.isNaN(idx) && idx >= 1 && idx <= this.choices.length) {
        return this.choices[idx - 1]?.value;
      }
      process.stderr.write(
        `${formatError(`Please enter a number between 1 and ${this.choices.length}`)}\n`,
      );
    }
  }
}
