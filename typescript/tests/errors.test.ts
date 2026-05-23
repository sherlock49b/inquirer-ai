import { describe, it, expect } from "vitest";
import {
  InquirerAIError,
  ValidationError,
  InvalidChoiceError,
  PromptAbortedError,
  EditorError,
} from "../src/errors.js";

describe("Error hierarchy", () => {
  it("ValidationError extends InquirerAIError", () => {
    const err = new ValidationError("test");
    expect(err).toBeInstanceOf(InquirerAIError);
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("ValidationError");
  });

  it("InvalidChoiceError extends ValidationError", () => {
    const err = new InvalidChoiceError("test");
    expect(err).toBeInstanceOf(ValidationError);
    expect(err).toBeInstanceOf(InquirerAIError);
    expect(err.name).toBe("InvalidChoiceError");
  });

  it("PromptAbortedError extends InquirerAIError", () => {
    const err = new PromptAbortedError("test");
    expect(err).toBeInstanceOf(InquirerAIError);
    expect(err.name).toBe("PromptAbortedError");
    expect(err).not.toBeInstanceOf(ValidationError);
  });

  it("EditorError extends InquirerAIError", () => {
    const err = new EditorError("test");
    expect(err).toBeInstanceOf(InquirerAIError);
    expect(err.name).toBe("EditorError");
    expect(err).not.toBeInstanceOf(ValidationError);
  });

  it("all errors preserve message", () => {
    const msg = "something went wrong";
    expect(new InquirerAIError(msg).message).toBe(msg);
    expect(new ValidationError(msg).message).toBe(msg);
    expect(new InvalidChoiceError(msg).message).toBe(msg);
    expect(new PromptAbortedError(msg).message).toBe(msg);
    expect(new EditorError(msg).message).toBe(msg);
  });
});
