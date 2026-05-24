# inquirer-ai/rust

Interactive CLI prompts for humans and AI agents, written in Rust.

When stdin is a TTY, prompts render a full terminal UI with cursor navigation,
key bindings, and styled output (crossterm). When stdin is not a TTY
(or `INQUIRER_AI_MODE=agent`), prompts communicate via a JSON line protocol on
stdout/stdin so that AI agents can drive CLI tools programmatically.

## Install

Not yet published to crates.io. Add it as a git dependency:

```toml
[dependencies]
inquirer-ai = { git = "https://github.com/sherlock49b/inquirer-ai", subdirectory = "rust" }
```

Requires Rust 1.85+.

## Quick Start

```rust
use inquirer_ai::{text, TextConfig, Result};

fn main() -> Result<()> {
    let name = text(TextConfig {
        message: "Project name".into(),
        validate: Some(Box::new(|s: &str| {
            if s.is_empty() {
                Err("cannot be empty".into())
            } else {
                Ok(())
            }
        })),
        ..TextConfig::new("Project name")
    })?;
    println!("Creating project {name}");
    Ok(())
}
```

## Prompt Types

All 12 prompt types follow the same pattern: pass a config struct, get back a
typed `Result<T>`.

---

### Text

Single-line text input.

```rust
fn text(config: TextConfig) -> Result<String>
```

```rust
pub struct TextConfig {
    pub message: String,
    pub default: Option<String>,
    pub validate: Option<Box<dyn Fn(&str) -> std::result::Result<(), String>>>,
    pub filter: Option<Box<dyn Fn(String) -> String>>,
}
```

```rust
let name = text(TextConfig {
    default: Some("World".into()),
    filter: Some(Box::new(|s| s.trim().to_string())),
    ..TextConfig::new("Your name")
})?;
```

---

### Confirm

Yes/no boolean prompt.

```rust
fn confirm(config: ConfirmConfig) -> Result<bool>
```

```rust
pub struct ConfirmConfig {
    pub message: String,
    pub default: bool,
}
```

```rust
let ok = confirm(ConfirmConfig {
    default: true,
    ..ConfirmConfig::new("Continue?")
})?;
```

---

### Select

Single-choice list with cursor navigation (crossterm TUI in terminal mode).

```rust
fn select(config: SelectConfig) -> Result<Value>
```

```rust
pub struct SelectConfig {
    pub message: String,
    pub choices: Vec<ChoiceItem>,
    pub default: Option<Value>,
    pub page_size: usize,   // default: 10
    pub r#loop: bool,       // default: true
}
```

```rust
use inquirer_ai::{select, SelectConfig, Choice, ChoiceItem, Separator};
use serde_json::json;

let tmpl = select(SelectConfig {
    choices: vec![
        ChoiceItem::Choice(Choice::new("Web API", json!("web-api"))),
        ChoiceItem::Choice(Choice::new("CLI Tool", json!("cli-tool"))),
        ChoiceItem::Separator(Separator::new("-- Experimental --")),
        ChoiceItem::Choice(Choice::new("gRPC Service", json!("grpc"))),
    ],
    ..SelectConfig::new("Template", vec![])
})?;
```

Key bindings in terminal mode: `up`/`k`, `down`/`j`, `enter` to confirm,
`ctrl+c` to abort.

---

### Checkbox

Multi-select list with toggle (crossterm TUI in terminal mode).

```rust
fn checkbox(config: CheckboxConfig) -> Result<Vec<Value>>
```

```rust
pub struct CheckboxConfig {
    pub message: String,
    pub choices: Vec<ChoiceItem>,
    pub default: Vec<Value>,
    pub page_size: usize,   // default: 10
    pub r#loop: bool,       // default: true
}
```

```rust
use inquirer_ai::{checkbox, CheckboxConfig, Choice, ChoiceItem};
use serde_json::json;

let features = checkbox(CheckboxConfig {
    default: vec![json!("docker")],
    choices: vec![
        ChoiceItem::Choice(Choice::new("Docker support", json!("docker"))),
        ChoiceItem::Choice(Choice::new("CI/CD", json!("ci"))),
        ChoiceItem::Choice(Choice {
            name: "Load testing".into(),
            value: json!("load-test"),
            disabled: Some(json!("coming soon")),
            ..Choice::new("Load testing", json!("load-test"))
        }),
    ],
    ..CheckboxConfig::new("Features", vec![])
})?;
```

Key bindings: `space` to toggle, `a` to toggle all, `enter` to confirm.

---

### Password

Masked text input.

```rust
fn password(config: PasswordConfig) -> Result<String>
```

```rust
pub struct PasswordConfig {
    pub message: String,
    pub mask: Option<String>,   // default: Some("*")
}
```

```rust
let pw = password(PasswordConfig::new("API key"))?;
```

---

### Number

Numeric input with optional min/max bounds.

```rust
fn number(config: NumberConfig) -> Result<f64>
```

```rust
pub struct NumberConfig {
    pub message: String,
    pub default: Option<f64>,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub float_allowed: bool,    // default: true
}
```

```rust
let port = number(NumberConfig {
    default: Some(8080.0),
    min: Some(1024.0),
    max: Some(65535.0),
    float_allowed: false,
    ..NumberConfig::new("Port")
})?;
```

---

### Editor

Opens `$VISUAL`, `$EDITOR`, or `vi` for multi-line text input.

```rust
fn editor(config: EditorConfig) -> Result<String>
```

```rust
pub struct EditorConfig {
    pub message: String,
    pub default: Option<String>,
    pub postfix: String,    // file extension, default: ".txt"
}
```

```rust
let body = editor(EditorConfig {
    postfix: ".md".into(),
    ..EditorConfig::new("Commit message")
})?;
```

---

### Search

Searchable selection with a dynamic source closure.

```rust
fn search(config: SearchConfig) -> Result<Value>
```

```rust
pub type SearchSource = Box<dyn Fn(&str) -> Vec<ChoiceItem>>;

pub struct SearchConfig {
    pub message: String,
    pub source: SearchSource,   // required
    pub page_size: usize,       // default: 10
}
```

```rust
use inquirer_ai::{search, SearchConfig, Choice, ChoiceItem};
use serde_json::json;

let pkg = search(SearchConfig::new("Package", |term| {
    let all = vec![
        ("fmt", "fmt"),
        ("net/http", "net-http"),
        ("serde", "serde"),
    ];
    all.into_iter()
        .filter(|(name, _)| name.contains(term))
        .map(|(name, val)| ChoiceItem::Choice(Choice::new(name, json!(val))))
        .collect()
}))?;
```

---

### Rawlist

Numbered list -- the user selects by typing a number.

```rust
fn rawlist(config: RawlistConfig) -> Result<Value>
```

```rust
pub struct RawlistConfig {
    pub message: String,
    pub choices: Vec<Choice>,
}
```

```rust
use inquirer_ai::{rawlist, RawlistConfig, Choice, ChoiceItem};
use serde_json::json;

let env = rawlist(RawlistConfig::new(
    "Environment",
    vec![
        ChoiceItem::Choice(Choice::new("Development", json!("dev"))),
        ChoiceItem::Choice(Choice::new("Staging", json!("staging"))),
        ChoiceItem::Choice(Choice::new("Production", json!("prod"))),
    ],
))?;
```

---

### Expand

Compact key-based selection. Each choice has a single-character key.

```rust
fn expand(config: ExpandConfig) -> Result<Value>
```

```rust
pub struct ExpandChoice {
    pub key: String,
    pub name: String,
    pub value: Value,
}

pub struct ExpandConfig {
    pub message: String,
    pub choices: Vec<ExpandChoice>,
}
```

```rust
use inquirer_ai::{expand, ExpandConfig, ExpandChoice};
use serde_json::json;

let action = expand(ExpandConfig::new(
    "Conflict on file.txt",
    vec![
        ExpandChoice { key: "y".into(), name: "Overwrite".into(), value: json!("overwrite") },
        ExpandChoice { key: "n".into(), name: "Skip".into(), value: json!("skip") },
        ExpandChoice { key: "d".into(), name: "Show diff".into(), value: json!("diff") },
    ],
))?;
```

The user types `h` or `help` to see the full list.

---

### Path

File or directory path input.

```rust
fn path(config: PathConfig) -> Result<String>
```

```rust
pub struct PathConfig {
    pub message: String,
    pub default: Option<String>,
    pub only_directories: bool,
}
```

```rust
let dir = path(PathConfig {
    default: Some("./out".into()),
    only_directories: true,
    ..PathConfig::new("Output directory")
})?;
```

---

### Autocomplete

Text input with a suggestion list. Accepts any string, not only suggestions.

```rust
fn autocomplete(config: AutocompleteConfig) -> Result<String>
```

```rust
pub struct AutocompleteConfig {
    pub message: String,
    pub choices: Vec<String>,
    pub default: Option<String>,
}
```

```rust
let color = autocomplete(AutocompleteConfig::new(
    "Favorite color",
    vec!["red".into(), "green".into(), "blue".into(), "yellow".into()],
))?;
```

## Choices

List-based prompts (Select, Checkbox, Search, Rawlist) accept a `Vec<ChoiceItem>`.
`ChoiceItem` is an enum with two variants: `Choice` and `Separator`.

```rust
pub struct Choice {
    pub name: String,
    pub value: Value,
    pub disabled: Option<Value>,     // None = enabled, Some(true) or Some("reason") = disabled
    pub short: Option<String>,
    pub description: Option<String>,
}

pub struct Separator {
    pub kind: String,   // always "separator"
    pub text: String,   // defaults to "--------" via Default impl
}

pub enum ChoiceItem {
    Choice(Choice),
    Separator(Separator),
}
```

Disabled choices appear grayed out in the TUI and cannot be selected. Set
`disabled` to `Some(json!(true))` for a generic disable, or to
`Some(json!("coming soon"))` to show a reason.

```rust
use inquirer_ai::{Choice, ChoiceItem, Separator};
use serde_json::json;

let choices = vec![
    ChoiceItem::Choice(Choice::new("Enabled item", json!("a"))),
    ChoiceItem::Separator(Separator::default()),
    ChoiceItem::Choice(Choice {
        disabled: Some(json!("not yet available")),
        ..Choice::new("Disabled item", json!("b"))
    }),
];
```

## Validation

The `TextConfig` prompt accepts a `validate` closure that receives the current
input and returns `Ok(())` or `Err(message)`. In terminal mode the prompt
re-asks on failure; in agent mode a validation error is sent back and the agent
can retry (up to 3 attempts).

```rust
let name = text(TextConfig {
    validate: Some(Box::new(|s: &str| {
        if s.len() < 3 {
            Err("must be at least 3 characters".into())
        } else {
            Ok(())
        }
    })),
    ..TextConfig::new("Username")
})?;
```

Text also supports a `filter` closure that transforms the value before
validation:

```rust
let name = text(TextConfig {
    filter: Some(Box::new(|s| s.to_lowercase())),
    validate: Some(Box::new(|s: &str| {
        if s.len() < 3 {
            Err("must be at least 3 characters".into())
        } else {
            Ok(())
        }
    })),
    ..TextConfig::new("Username")
})?;
```

The `NumberConfig` prompt enforces `min`, `max`, and `float_allowed` constraints
automatically. Select and Checkbox prompts validate that the answer matches one
of the enabled choices.

## Agent Protocol

When `is_agent_mode()` returns true (non-TTY stdin, or `INQUIRER_AI_MODE=agent`),
every prompt communicates over a JSONL protocol on stdout/stdin instead of
rendering a terminal UI.

1. On the first prompt call the library emits a **handshake** line:

```json
{"kind":"handshake","protocol":"inquirer-ai","version":"0.2.0","format":"jsonl","interaction":"sequential","description":"...","example_response":{"answer":"<value>"}}
```

2. Each prompt emits a **question** JSON line on stdout:

```json
{"kind":"prompt","type":"select","message":"Template","choices":[{"name":"Web API","value":"web-api"},{"name":"CLI Tool","value":"cli-tool"}],"step":1,"total":null}
```

3. The agent replies with a single JSON line on stdin:

```json
{"answer":"web-api"}
```

4. The next prompt emits the next question, and so on (sequential,
   one-at-a-time).

This is the same JSONL protocol used by the Python and Go `inquirer-ai`
packages. See [spec/protocol.md](../spec/protocol.md) for the full
specification.

`is_agent_mode()` can be forced with the environment variable:

```sh
INQUIRER_AI_MODE=agent ./myapp   # force agent mode
INQUIRER_AI_MODE=human ./myapp   # force terminal mode
```

Custom file descriptors can be specified for agent I/O via `INQUIRER_AI_FD_OUT`
and `INQUIRER_AI_FD_IN` environment variables.

## Error Handling

All prompt functions return `Result<T>`, which is an alias for
`std::result::Result<T, InquirerError>`.

```rust
#[derive(Debug)]
pub enum InquirerError {
    Validation(String),     // validate callback rejected input
    InvalidChoice(String),  // answer not in choice list
    PromptAborted(String),  // user pressed Ctrl+C or stdin closed
    Editor(String),         // $EDITOR process failed
    Io(std::io::Error),     // underlying I/O error
}
```

`InquirerError` implements `Display`, `Error`, and `From<std::io::Error>` /
`From<serde_json::Error>`.

```rust
use inquirer_ai::{select, SelectConfig, InquirerError};

let result = select(cfg);
match result {
    Ok(val) => println!("Selected: {val}"),
    Err(InquirerError::PromptAborted(_)) => {
        eprintln!("User cancelled.");
        std::process::exit(0);
    }
    Err(e) => {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}
```

## Theming

`DEFAULT_THEME` controls colors and symbols used in prompt rendering. The
`Theme` struct is defined as:

```rust
pub struct Theme {
    pub question: &'static str,     // hex color for question prefix     (default "#9fa4e3")
    pub success: &'static str,      // hex color for success prefix      (default "#62bfa1")
    pub highlight: &'static str,    // hex color for focused item        (default "#90bbe9")
    pub selected: &'static str,     // hex color for checked items       (default "#59bca4")
    pub answer: &'static str,       // hex color for confirmed answer    (default "#9db9dd")
    pub error: &'static str,        // hex color for validation errors   (default "#d77780")
    pub muted: &'static str,        // hex color for hints/disabled      (default "#84858f")
    pub sym_question: &'static str, // question prefix symbol            (default "?")
    pub sym_success: &'static str,  // success prefix symbol             (default "✓")
    pub sym_pointer: &'static str,  // cursor indicator in lists         (default "❯")
    pub sym_checked: &'static str,  // checked checkbox mark             (default "◉")
    pub sym_unchecked: &'static str,// unchecked checkbox mark           (default "◯")
}
```

Colors are specified as hex strings and converted to ANSI true-color (24-bit)
escape sequences at render time.

The TUI supports:

- **Pagination** -- long lists scroll with "(more above)" / "(more below)"
  indicators, controlled by `page_size` (default 10).
- **Loop** -- when `loop` is true (the default), the cursor wraps from last
  to first item and vice versa.
- **Disabled items** -- shown in muted style, cannot be selected.
- **Separators** -- rendered as divider lines between choice groups.

## License

MIT. See [LICENSE](./LICENSE).
