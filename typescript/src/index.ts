export {
  InquirerAIError,
  ValidationError,
  InvalidChoiceError,
  PromptAbortedError,
  EditorError,
} from "./errors.js";

export { isAgentMode } from "./mode.js";
export { type Theme, setTheme, getTheme } from "./theme.js";
export { type Choice, type Separator, type ChoiceItem, type RawChoice, createSeparator } from "./choice.js";
export { resetAgent } from "./agent.js";

export { TextPrompt, type TextConfig } from "./prompts/text.js";
export { ConfirmPrompt, type ConfirmConfig } from "./prompts/confirm.js";
export { SelectPrompt, type SelectConfig } from "./prompts/select.js";
export { CheckboxPrompt, type CheckboxConfig } from "./prompts/checkbox.js";
export { PasswordPrompt, type PasswordConfig } from "./prompts/password.js";
export { NumberPrompt, type NumberConfig } from "./prompts/number.js";
export { EditorPrompt, type EditorConfig } from "./prompts/editor.js";
export { SearchPrompt, type SearchConfig } from "./prompts/search.js";
export { RawlistPrompt, type RawlistConfig } from "./prompts/rawlist.js";
export { ExpandPrompt, type ExpandConfig, type ExpandChoice } from "./prompts/expand.js";
export { PathPrompt, type PathConfig } from "./prompts/path.js";
export { AutocompletePrompt, type AutocompleteConfig } from "./prompts/autocomplete.js";

export type { ValidateFn, FilterFn, TransformerFn } from "./prompts/base.js";

import { TextPrompt, type TextConfig } from "./prompts/text.js";
import { ConfirmPrompt, type ConfirmConfig } from "./prompts/confirm.js";
import { SelectPrompt, type SelectConfig } from "./prompts/select.js";
import { CheckboxPrompt, type CheckboxConfig } from "./prompts/checkbox.js";
import { PasswordPrompt, type PasswordConfig } from "./prompts/password.js";
import { NumberPrompt, type NumberConfig } from "./prompts/number.js";
import { EditorPrompt, type EditorConfig } from "./prompts/editor.js";
import { SearchPrompt, type SearchConfig } from "./prompts/search.js";
import { RawlistPrompt, type RawlistConfig } from "./prompts/rawlist.js";
import { ExpandPrompt, type ExpandConfig } from "./prompts/expand.js";
import { PathPrompt, type PathConfig } from "./prompts/path.js";
import { AutocompletePrompt, type AutocompleteConfig } from "./prompts/autocomplete.js";

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
