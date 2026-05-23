export class InquirerAIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InquirerAIError";
  }
}

export class ValidationError extends InquirerAIError {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

export class InvalidChoiceError extends ValidationError {
  constructor(message: string) {
    super(message);
    this.name = "InvalidChoiceError";
  }
}

export class PromptAbortedError extends InquirerAIError {
  constructor(message: string) {
    super(message);
    this.name = "PromptAbortedError";
  }
}

export class EditorError extends InquirerAIError {
  constructor(message: string) {
    super(message);
    this.name = "EditorError";
  }
}
