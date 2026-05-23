import { isAgentMode } from "../mode.js";
import { agentSend, agentReceive, agentSendValidationError } from "../agent.js";
import { PromptAbortedError, ValidationError } from "../errors.js";
import { formatSuccess } from "../terminal.js";

const MAX_AGENT_RETRIES = 3;

export type ValidateFn<T> = (value: T) => boolean | string | null | undefined;
export type FilterFn<T> = (value: T) => T;
export type TransformerFn<T> = (value: T) => string;

export interface BaseConfig<T> {
  message: string;
  default?: T | null;
  validate?: ValidateFn<T>;
  filter?: FilterFn<T>;
  transformer?: TransformerFn<T>;
}

export abstract class BasePrompt<T> {
  protected message: string;
  protected defaultValue: T | null;
  protected validateFn?: ValidateFn<T>;
  protected filterFn?: FilterFn<T>;
  protected transformerFn?: TransformerFn<T>;

  constructor(config: BaseConfig<T>) {
    this.message = config.message;
    this.defaultValue = config.default ?? null;
    this.validateFn = config.validate;
    this.filterFn = config.filter;
    this.transformerFn = config.transformer;
  }

  abstract get promptType(): string;
  protected abstract executeTerminal(): Promise<T>;
  protected abstract validateAnswer(value: unknown): T;

  protected formatAnswer(value: T): string {
    return String(value);
  }

  protected toAgentDict(): Record<string, unknown> {
    return {
      type: this.promptType,
      message: this.message,
      default: this.defaultValue,
    };
  }

  protected async executeAgent(): Promise<T> {
    for (let attempt = 0; attempt <= MAX_AGENT_RETRIES; attempt++) {
      await agentSend(this.toAgentDict());
      let answer: unknown;
      try {
        answer = await agentReceive();
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (msg.includes("stdin closed")) throw new PromptAbortedError(msg);
        throw new ValidationError(msg);
      }
      try {
        return this.validateAnswer(answer);
      } catch (err) {
        if (err instanceof ValidationError && attempt < MAX_AGENT_RETRIES) {
          agentSendValidationError(err.message);
          continue;
        }
        throw err;
      }
    }
    // Should not reach here, but satisfy TypeScript
    throw new ValidationError("Maximum validation retries exceeded");
  }

  protected runUserValidation(value: T): string | null {
    if (!this.validateFn) return null;
    const result = this.validateFn(value);
    if (result === true || result === null || result === undefined) return null;
    if (typeof result === "string") return result;
    return "Validation failed";
  }

  async execute(): Promise<T> {
    const agent = isAgentMode();
    let userValidationRetries = 0;

    while (true) {
      let result: T;
      try {
        result = agent ? await this.executeAgent() : await this.executeTerminal();
      } catch (err) {
        if (err instanceof PromptAbortedError) throw err;
        if (err instanceof ValidationError) throw err;
        throw new PromptAbortedError("Prompt aborted (stdin closed)");
      }

      if (this.filterFn) {
        result = this.filterFn(result);
      }

      const error = this.runUserValidation(result);
      if (error) {
        if (agent) {
          userValidationRetries++;
          if (userValidationRetries > MAX_AGENT_RETRIES) {
            throw new ValidationError(error);
          }
          agentSendValidationError(error);
          continue;
        }
        process.stderr.write(
          `\x1b[38;2;215;119;128m  ${error}\x1b[0m\n`,
        );
        continue;
      }

      if (!agent) {
        const display = this.transformerFn
          ? this.transformerFn(result)
          : this.formatAnswer(result);
        process.stderr.write(formatSuccess(this.message, display) + "\n");
      }

      return result;
    }
  }
}
