import {
  agentNextStep,
  agentReceive,
  agentSend,
  agentSendError,
  agentSendValidationError,
} from "../agent.js";
import { PromptAbortedError, ValidationError } from "../errors.js";
import { isAgentMode } from "../mode.js";
import { getSocketTransport } from "../socket.js";
import { formatError, formatSuccess } from "../terminal.js";

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

  /**
   * Async variant of {@link toAgentDict}. Defaults to the synchronous payload,
   * but prompts with async-resolved data (e.g. search with an async source)
   * override this so the socket transport advertises the resolved payload (R6).
   */
  protected async buildAgentDict(): Promise<Record<string, unknown>> {
    return this.toAgentDict();
  }

  protected async executeAgent(): Promise<T> {
    // Single unified budget: MAX_AGENT_RETRIES total answer attempts per prompt.
    // Type-coercion validation AND user validate() failures share this counter,
    // mirroring the socket transport's promptCycle (R1).
    const dict = await this.buildAgentDict();
    // Advance the logical prompt counter ONCE; every re-send within this retry
    // loop reuses the same step value so a prompt and all of its validation
    // re-sends share an identical "step".
    const step = agentNextStep();
    for (let attempt = 1; attempt <= MAX_AGENT_RETRIES; attempt++) {
      await agentSend(dict, step);
      let answer: unknown;
      try {
        answer = await agentReceive();
      } catch (err) {
        // Empty line / EOF / closed stdin / malformed protocol line = immediate
        // fatal abort (not a retry); emit a fatal error frame (R1).
        const msg = err instanceof Error ? err.message : String(err);
        agentSendError(msg);
        if (msg.includes("stdin closed")) throw new PromptAbortedError(msg);
        throw new ValidationError(msg);
      }

      let result: T;
      try {
        result = this.validateAnswer(answer);
      } catch (err) {
        if (err instanceof ValidationError) {
          // Attempts 1 & 2 -> validation_error; attempt 3 -> fatal error (R1).
          if (attempt < MAX_AGENT_RETRIES) {
            agentSendValidationError(err.message);
            continue;
          }
          agentSendError(err.message);
        }
        throw err;
      }

      // User validation runs on the coerced value and shares the same unified
      // budget as type coercion (R1, R11). A validate() that RETURNS a
      // string/false, or THROWS a ValidationError, is a retryable validation
      // failure. A validate() that THROWS a non-ValidationError is fatal: it is
      // reported as {"kind":"error"} and re-thrown (R10).
      if (this.validateFn) {
        let error: string | null = null;
        try {
          const r = this.validateFn(result);
          if (typeof r === "string") error = r;
          else if (r === false) error = "Validation failed";
        } catch (err) {
          if (err instanceof ValidationError) {
            error = err.message;
          } else {
            const msg = err instanceof Error ? err.message : String(err);
            agentSendError(msg);
            throw new ValidationError(msg);
          }
        }
        if (error) {
          if (attempt < MAX_AGENT_RETRIES) {
            agentSendValidationError(error);
            continue;
          }
          agentSendError(error);
          throw new ValidationError(error);
        }
      }
      return result;
    }
    // Should not reach here, but satisfy TypeScript
    throw new ValidationError("Maximum validation retries exceeded");
  }

  protected runUserValidation(value: T): string | null {
    if (!this.validateFn) return null;
    let result: boolean | string | null | undefined;
    try {
      result = this.validateFn(value);
    } catch (err) {
      if (err instanceof ValidationError) throw err;
      const msg = err instanceof Error ? err.message : String(err);
      throw new ValidationError(msg);
    }
    if (result === true || result === null || result === undefined) return null;
    if (typeof result === "string") return result;
    return "Validation failed";
  }

  async execute(): Promise<T> {
    // Socket transport takes priority when available
    const transport = getSocketTransport();
    if (transport) {
      const dict = await this.buildAgentDict();
      return transport.promptCycle<T>(
        { kind: "prompt", ...dict },
        (value: unknown) => this.validateAnswer(value),
        this.filterFn ?? null,
        this.validateFn ?? null,
      );
    }

    const agent = isAgentMode();

    if (agent) {
      // executeAgent runs type coercion AND user validation under a single
      // unified retry budget (R1). Filter is applied only on the accepted value.
      let result: T;
      try {
        result = await this.executeAgent();
      } catch (err) {
        if (err instanceof PromptAbortedError) throw err;
        if (err instanceof ValidationError) throw err;
        throw new PromptAbortedError("Prompt aborted (stdin closed)");
      }
      if (this.filterFn) {
        result = this.filterFn(result);
      }
      return result;
    }

    while (true) {
      let result: T;
      try {
        result = await this.executeTerminal();
      } catch (err) {
        if (err instanceof PromptAbortedError) throw err;
        if (err instanceof ValidationError) throw err;
        throw new PromptAbortedError("Prompt aborted (stdin closed)");
      }

      const error = this.runUserValidation(result);
      if (error) {
        process.stderr.write(`${formatError(error)}\n`);
        continue;
      }

      if (this.filterFn) {
        result = this.filterFn(result);
      }

      const display = this.transformerFn
        ? this.transformerFn(result)
        : this.formatAnswer(result);
      process.stderr.write(`${formatSuccess(this.message, display)}\n`);

      return result;
    }
  }
}
