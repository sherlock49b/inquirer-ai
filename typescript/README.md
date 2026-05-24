# inquirer-ai

Interactive CLI prompts for humans and AI agents, written in TypeScript.

When stdin is a TTY, prompts render a terminal UI with cursor navigation,
key bindings, and styled output. When stdin is not a TTY
(or `INQUIRER_AI_MODE=agent`), prompts communicate via a JSON line protocol on
stdout/stdin so that AI agents can drive CLI tools programmatically.

## Install

```sh
npm install inquirer-ai
```

Requires Node.js 18+.

## Quick Start

```typescript
import { text, confirm, select } from "inquirer-ai";

const name = await text({
  message: "Project name",
  validate: (s) => (s.length > 0 ? true : "Cannot be empty"),
});

const useTS = await confirm({
  message: "Use TypeScript?",
  default: true,
});

const template = await select({
  message: "Template",
  choices: [
    { name: "Web API", value: "web-api" },
    { name: "CLI Tool", value: "cli-tool" },
  ],
});

console.log(`Creating ${name} with template ${template} (TS: ${useTS})`);
```

## Prompt Types

All 12 prompt types follow the same pattern: pass a config object, get back a
typed promise.

---

### Text

Single-line text input.

```typescript
function text(config: TextConfig): Promise<string>
```

```typescript
interface TextConfig {
  message: string;
  default?: string | null;
  validate?: ValidateFn<string>;
  filter?: FilterFn<string>;
  transformer?: TransformerFn<string>;
}
```

```typescript
import { text } from "inquirer-ai";

const name = await text({
  message: "Your name",
  default: "World",
  filter: (s) => s.trim(),
});
```

---

### Confirm

Yes/no boolean prompt.

```typescript
function confirm(config: ConfirmConfig): Promise<boolean>
```

```typescript
interface ConfirmConfig {
  message: string;
  default?: boolean | null;  // default: false
  validate?: ValidateFn<boolean>;
  filter?: FilterFn<boolean>;
  transformer?: TransformerFn<boolean>;
}
```

```typescript
import { confirm } from "inquirer-ai";

const ok = await confirm({
  message: "Continue?",
  default: true,
});
```

---

### Select

Single-choice list with cursor navigation.

```typescript
function select<V = unknown>(config: SelectConfig<V>): Promise<V>
```

```typescript
interface SelectConfig<V = unknown> {
  message: string;
  choices: RawChoice<V>[];
  default?: V | null;
  pageSize?: number;   // default: 10
  loop?: boolean;      // default: true
  validate?: ValidateFn<V>;
  filter?: FilterFn<V>;
  transformer?: TransformerFn<V>;
}
```

```typescript
import { select, createSeparator } from "inquirer-ai";

const tmpl = await select({
  message: "Template",
  choices: [
    { name: "Web API", value: "web-api", description: "FastAPI + PostgreSQL" },
    { name: "CLI Tool", value: "cli-tool" },
    createSeparator("── Experimental ──"),
    { name: "gRPC Service", value: "grpc" },
  ],
});
```

Key bindings in terminal mode: `up`/`k`, `down`/`j`, `enter` to confirm,
`ctrl+c` to abort.

---

### Checkbox

Multi-select list with toggle.

```typescript
function checkbox<V = unknown>(config: CheckboxConfig<V>): Promise<V[]>
```

```typescript
interface CheckboxConfig<V = unknown> {
  message: string;
  choices: RawChoice<V>[];
  default?: V[] | null;
  pageSize?: number;   // default: 10
  loop?: boolean;      // default: true
  validate?: ValidateFn<V[]>;
  filter?: FilterFn<V[]>;
  transformer?: TransformerFn<V[]>;
}
```

```typescript
import { checkbox } from "inquirer-ai";

const features = await checkbox({
  message: "Features",
  default: ["docker"],
  choices: [
    { name: "Docker support", value: "docker" },
    { name: "CI/CD", value: "ci" },
    { name: "Load testing", value: "load-test", disabled: "coming soon" },
  ],
});
```

Key bindings: `space` to toggle, `a` to toggle all, `enter` to confirm.

---

### Password

Masked text input.

```typescript
function password(config: PasswordConfig): Promise<string>
```

```typescript
interface PasswordConfig {
  message: string;
  mask?: string | null;  // default: "*"
  validate?: ValidateFn<string>;
  filter?: FilterFn<string>;
  transformer?: TransformerFn<string>;
}
```

```typescript
import { password } from "inquirer-ai";

const pw = await password({
  message: "API key",
});
```

---

### Number

Numeric input with optional min/max bounds.

```typescript
function number(config: NumberConfig): Promise<number>
```

```typescript
interface NumberConfig {
  message: string;
  default?: number | null;
  min?: number | null;
  max?: number | null;
  floatAllowed?: boolean;  // default: true
  validate?: ValidateFn<number>;
  filter?: FilterFn<number>;
  transformer?: TransformerFn<number>;
}
```

```typescript
import { number } from "inquirer-ai";

const port = await number({
  message: "Port",
  default: 8080,
  min: 1024,
  max: 65535,
  floatAllowed: false,
});
```

---

### Editor

Opens `$VISUAL`, `$EDITOR`, or `vi` for multi-line text input.

```typescript
function editor(config: EditorConfig): Promise<string>
```

```typescript
interface EditorConfig {
  message: string;
  default?: string | null;
  postfix?: string;  // file extension, default: ".txt"
  validate?: ValidateFn<string>;
  filter?: FilterFn<string>;
  transformer?: TransformerFn<string>;
}
```

```typescript
import { editor } from "inquirer-ai";

const body = await editor({
  message: "Commit message",
  postfix: ".md",
});
```

---

### Search

Searchable selection with a dynamic source function.

```typescript
function search(config: SearchConfig): Promise<unknown>
```

```typescript
interface SearchConfig {
  message: string;
  source: (term: string) => RawChoice[];  // required
  pageSize?: number;                       // default: 10
  validate?: ValidateFn<unknown>;
  filter?: FilterFn<unknown>;
  transformer?: TransformerFn<unknown>;
}
```

```typescript
import { search } from "inquirer-ai";

const pkg = await search({
  message: "Package",
  source: (term) => {
    const all = ["express", "fastify", "koa", "hapi"];
    return all
      .filter((p) => p.includes(term))
      .map((p) => ({ name: p, value: p }));
  },
});
```

---

### Rawlist

Numbered list -- the user selects by typing a number.

```typescript
function rawlist(config: RawlistConfig): Promise<unknown>
```

```typescript
interface RawlistConfig {
  message: string;
  choices: RawChoice[];
  validate?: ValidateFn<unknown>;
  filter?: FilterFn<unknown>;
  transformer?: TransformerFn<unknown>;
}
```

```typescript
import { rawlist } from "inquirer-ai";

const env = await rawlist({
  message: "Environment",
  choices: [
    { name: "Development", value: "dev" },
    { name: "Staging", value: "staging" },
    { name: "Production", value: "prod" },
  ],
});
```

---

### Expand

Compact key-based selection. Each choice has a single-character key.

```typescript
function expand(config: ExpandConfig): Promise<unknown>
```

```typescript
interface ExpandChoice {
  key: string;
  name: string;
  value: unknown;
}

interface ExpandConfig {
  message: string;
  choices: ExpandChoice[];
  validate?: ValidateFn<unknown>;
  filter?: FilterFn<unknown>;
  transformer?: TransformerFn<unknown>;
}
```

```typescript
import { expand } from "inquirer-ai";

const action = await expand({
  message: "Conflict on file.txt",
  choices: [
    { key: "y", name: "Overwrite", value: "overwrite" },
    { key: "n", name: "Skip", value: "skip" },
    { key: "d", name: "Show diff", value: "diff" },
  ],
});
```

The user types `h` or `help` to see the full list.

---

### Path

File or directory path input.

```typescript
function path(config: PathConfig): Promise<string>
```

```typescript
interface PathConfig {
  message: string;
  default?: string | null;
  onlyDirectories?: boolean;  // default: false
  validate?: ValidateFn<string>;
  filter?: FilterFn<string>;
  transformer?: TransformerFn<string>;
}
```

```typescript
import { path } from "inquirer-ai";

const dir = await path({
  message: "Output directory",
  default: "./out",
  onlyDirectories: true,
});
```

---

### Autocomplete

Text input with a suggestion list. Accepts any string, not only suggestions.

```typescript
function autocomplete(config: AutocompleteConfig): Promise<string>
```

```typescript
interface AutocompleteConfig {
  message: string;
  choices: string[];
  default?: string | null;
  validate?: ValidateFn<string>;
  filter?: FilterFn<string>;
  transformer?: TransformerFn<string>;
}
```

```typescript
import { autocomplete } from "inquirer-ai";

const color = await autocomplete({
  message: "Favorite color",
  choices: ["red", "green", "blue", "yellow"],
});
```

## Choices

List-based prompts (Select, Checkbox, Search, Rawlist) accept a `RawChoice<V>[]`
array. A `RawChoice` is a union of `string | Choice<V> | Separator`.

```typescript
interface Choice<V = unknown> {
  name: string;
  value: V;
  disabled?: boolean | string;
  short?: string;
  description?: string;
}

interface Separator {
  type: "separator";
  text: string;
}

type RawChoice<V = unknown> = string | Choice<V> | Separator;
```

Use `createSeparator` to create a separator with a default or custom divider:

```typescript
import { createSeparator } from "inquirer-ai";

createSeparator();                      // "────────"
createSeparator("── Experimental ──");  // custom text
```

Passing a plain string as a choice is shorthand for `{ name: s, value: s }`.

Disabled choices appear grayed out in the terminal UI and cannot be selected.
Set `disabled` to `true` for a generic disable, or to a string (e.g.
`"coming soon"`) to show a reason.

## Validation, Filter, and Transformer

All config types extend `BaseConfig<T>`, which accepts three optional callbacks:

```typescript
type ValidateFn<T>     = (value: T) => boolean | string | null | undefined;
type FilterFn<T>       = (value: T) => T;
type TransformerFn<T>  = (value: T) => string;
```

- **Filter** runs first and transforms the raw answer before validation.
- **Validate** runs second. Return `true`, `null`, or `undefined` to accept.
  Return a string to reject with that string as the error message. In terminal
  mode the prompt re-asks; in agent mode a validation error is sent back to the
  agent (up to 3 retries).
- **Transformer** controls how the confirmed answer is displayed in the
  terminal. It does not affect the returned value.

```typescript
import { text } from "inquirer-ai";

const username = await text({
  message: "Username",
  filter: (s) => s.toLowerCase().trim(),
  validate: (s) => (s.length >= 3 ? true : "Must be at least 3 characters"),
  transformer: (s) => s.toUpperCase(),
});
```

## Agent Protocol

When `isAgentMode()` returns `true` (non-TTY stdin, or
`INQUIRER_AI_MODE=agent`), every prompt communicates over a JSONL protocol on
stdout/stdin instead of rendering a terminal UI.

1. On the first prompt call the library emits a **handshake** line:

```json
{"kind":"handshake","protocol":"inquirer-ai","version":"0.2.0","format":"jsonl","interaction":"sequential","total":null,"description":"...","example_response":{"answer":"<value>"}}
```

2. Each prompt emits a **question** JSON line on stdout:

```json
{"kind":"prompt","step":1,"total":null,"type":"select","message":"Template","choices":[{"name":"Web API","value":"web-api"},{"name":"CLI Tool","value":"cli-tool"}]}
```

3. The agent replies with a single JSON line on stdin:

```json
{"answer":"web-api"}
```

4. The next prompt emits the next question, and so on (sequential,
   one-at-a-time).

This is the same JSONL protocol used by the Go and Python `inquirer-ai`
packages. See [spec/protocol.md](../spec/protocol.md) for the full
specification.

### Mode detection

`isAgentMode()` auto-detects based on whether stdin is a TTY. Override with
the environment variable:

```sh
INQUIRER_AI_MODE=agent node myapp.js   # force agent mode
INQUIRER_AI_MODE=human node myapp.js   # force terminal mode
```

### Custom file descriptors

The agent protocol reads/writes on stdin/stdout by default. Override with
environment variables to use separate file descriptors:

```sh
INQUIRER_AI_FD_OUT=3 INQUIRER_AI_FD_IN=4 node myapp.js
```

## Error Handling

All prompt functions throw on failure. The library defines an error hierarchy
rooted at `InquirerAIError`:

```typescript
class InquirerAIError extends Error {}
class ValidationError extends InquirerAIError {}
class InvalidChoiceError extends ValidationError {}
class PromptAbortedError extends InquirerAIError {}
class EditorError extends InquirerAIError {}
```

| Error | When |
|---|---|
| `PromptAbortedError` | User pressed Ctrl+C or stdin closed |
| `ValidationError` | Validate callback rejected input / agent retries exhausted |
| `InvalidChoiceError` | Answer not in the choice list |
| `EditorError` | `$EDITOR` process failed or not found |

```typescript
import { select, PromptAbortedError } from "inquirer-ai";

try {
  const result = await select(config);
} catch (err) {
  if (err instanceof PromptAbortedError) {
    console.log("User cancelled.");
    process.exit(0);
  }
  throw err;
}
```

## Theming

`setTheme` overrides the default theme. Call it at program start to customize
colors and symbols.

```typescript
import { setTheme, type Theme } from "inquirer-ai";
```

```typescript
interface Theme {
  question: string;     // hex color for the question prefix    (default "#9fa4e3")
  success: string;      // hex color for success prefix         (default "#62bfa1")
  pointer: string;      // hex color for cursor arrow           (default "#9c99ec")
  highlight: string;    // hex color for focused item text      (default "#90bbe9")
  selected: string;     // hex color for checked items          (default "#59bca4")
  answer: string;       // hex color for confirmed answer       (default "#9db9dd")
  error: string;        // hex color for validation errors      (default "#d77780")
  muted: string;        // hex color for hints, disabled items  (default "#84858f")
  symQuestion: string;  // prefix for the question line         (default "?")
  symSuccess: string;   // prefix after successful answer       (default "✓")
  symPointer: string;   // cursor indicator in lists            (default "❯")
  symChecked: string;   // checked checkbox mark                (default "◉")
  symUnchecked: string; // unchecked checkbox mark              (default "◯")
}
```

```typescript
setTheme({
  symQuestion: ">",
  symSuccess: "[ok]",
  symPointer: "->",
  symChecked: "[x]",
  symUnchecked: "[ ]",
});
```

`setTheme` accepts a `Partial<Theme>`, so you only need to specify the fields
you want to change. Use `getTheme()` to read the current theme.

## License

MIT
