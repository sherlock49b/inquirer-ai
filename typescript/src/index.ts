export { agentSendError, agentSendValidationError, getHandshakeAck, resetAgent } from "./agent.js";
export { type Choice, type ChoiceItem, createSeparator, type RawChoice, type Separator } from "./choice.js";
export {
  EditorError,
  InquirerAIError,
  InvalidChoiceError,
  PromptAbortedError,
  ValidationError,
} from "./errors.js";
export { isAgentMode } from "./mode.js";
export { type AutocompleteConfig, AutocompletePrompt } from "./prompts/autocomplete.js";
export type { FilterFn, TransformerFn, ValidateFn } from "./prompts/base.js";
export { type CheckboxConfig, CheckboxPrompt } from "./prompts/checkbox.js";
export { type ConfirmConfig, ConfirmPrompt } from "./prompts/confirm.js";
export { type EditorConfig, EditorPrompt } from "./prompts/editor.js";
export { type ExpandChoice, type ExpandConfig, ExpandPrompt } from "./prompts/expand.js";
export { type NumberConfig, NumberPrompt } from "./prompts/number.js";
export { type PasswordConfig, PasswordPrompt } from "./prompts/password.js";
export { type PathConfig, PathPrompt } from "./prompts/path.js";
export { type RawlistConfig, RawlistPrompt } from "./prompts/rawlist.js";
export { type SearchConfig, SearchPrompt } from "./prompts/search.js";
export { type SelectConfig, SelectPrompt } from "./prompts/select.js";
export { type TextConfig, TextPrompt } from "./prompts/text.js";
export { getSocketTransport, resetSocketTransport, SocketTransport } from "./socket.js";
export { getTheme, setTheme, type Theme } from "./theme.js";

import { type AutocompleteConfig, AutocompletePrompt } from "./prompts/autocomplete.js";
import { type CheckboxConfig, CheckboxPrompt } from "./prompts/checkbox.js";
import { type ConfirmConfig, ConfirmPrompt } from "./prompts/confirm.js";
import { type EditorConfig, EditorPrompt } from "./prompts/editor.js";
import { type ExpandConfig, ExpandPrompt } from "./prompts/expand.js";
import { type NumberConfig, NumberPrompt } from "./prompts/number.js";
import { type PasswordConfig, PasswordPrompt } from "./prompts/password.js";
import { type PathConfig, PathPrompt } from "./prompts/path.js";
import { type RawlistConfig, RawlistPrompt } from "./prompts/rawlist.js";
import { type SearchConfig, SearchPrompt } from "./prompts/search.js";
import { type SelectConfig, SelectPrompt } from "./prompts/select.js";
import { type TextConfig, TextPrompt } from "./prompts/text.js";

export async function text(config: TextConfig): Promise<string> {
  return new TextPrompt(config).execute();
}

export async function confirm(config: ConfirmConfig): Promise<boolean> {
  return new ConfirmPrompt(config).execute();
}

export async function select<V = unknown>(config: SelectConfig<V>): Promise<V> {
  return new SelectPrompt(config).execute();
}

export async function checkbox<V = unknown>(config: CheckboxConfig<V>): Promise<V[]> {
  return new CheckboxPrompt(config).execute();
}

export async function password(config: PasswordConfig): Promise<string> {
  return new PasswordPrompt(config).execute();
}

export async function number(config: NumberConfig): Promise<number> {
  return new NumberPrompt(config).execute();
}

export async function editor(config: EditorConfig): Promise<string> {
  return new EditorPrompt(config).execute();
}

export async function search(config: SearchConfig): Promise<unknown> {
  return new SearchPrompt(config).execute();
}

export async function rawlist(config: RawlistConfig): Promise<unknown> {
  return new RawlistPrompt(config).execute();
}

export async function expand(config: ExpandConfig): Promise<unknown> {
  return new ExpandPrompt(config).execute();
}

export async function path(config: PathConfig): Promise<string> {
  return new PathPrompt(config).execute();
}

export async function autocomplete(config: AutocompleteConfig): Promise<string> {
  return new AutocompletePrompt(config).execute();
}
