# inquirer-ai/go

Interactive CLI prompts for humans and AI agents, written in Go.

When stdin is a TTY, prompts render a full terminal UI with cursor navigation,
key bindings, and styled output (bubbletea + lipgloss). When stdin is not a TTY
(or `INQUIRER_AI_MODE=agent`), prompts communicate via a JSON line protocol on
stdout/stdin so that AI agents can drive CLI tools programmatically.

## Install

```sh
go get github.com/sherlock49b/inquirer-ai/go/prompt
```

Requires Go 1.22+.

## Quick Start

```go
package main

import (
	"fmt"
	"os"

	"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
	name, err := prompt.Text(prompt.TextConfig{
		Message: "Project name",
		Validate: func(s string) error {
			if s == "" {
				return fmt.Errorf("cannot be empty")
			}
			return nil
		},
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Creating project %s\n", name)
}
```

## Prompt Types

All 12 prompt types follow the same pattern: pass a config struct, get back a
typed value and an error.

---

### Text

Single-line text input.

```go
func Text(cfg TextConfig) (string, error)
```

```go
type TextConfig struct {
	Message  string
	Default  string
	Validate func(string) error
	Filter   func(string) string
}
```

```go
name, err := prompt.Text(prompt.TextConfig{
	Message: "Your name",
	Default: "World",
	Filter:  strings.TrimSpace,
})
```

---

### Confirm

Yes/no boolean prompt.

```go
func Confirm(cfg ConfirmConfig) (bool, error)
```

```go
type ConfirmConfig struct {
	Message  string
	Default  bool
	Validate func(any) error
	Filter   func(any) any
}
```

```go
ok, err := prompt.Confirm(prompt.ConfirmConfig{
	Message: "Continue?",
	Default: true,
})
```

---

### Select

Single-choice list with cursor navigation (bubbletea TUI in terminal mode).

```go
func Select(cfg SelectConfig) (any, error)
```

```go
type SelectConfig struct {
	Message  string
	Choices  []ChoiceItem
	Default  string
	PageSize int    // default: 10
	Loop     *bool  // default: true
	Validate func(any) error
	Filter   func(any) any
}
```

```go
tmpl, err := prompt.Select(prompt.SelectConfig{
	Message: "Template",
	Choices: []prompt.ChoiceItem{
		prompt.Choice{Name: "Web API", Value: "web-api", Description: "FastAPI + PostgreSQL"},
		prompt.Choice{Name: "CLI Tool", Value: "cli-tool"},
		prompt.Separator{Text: "── Experimental ──"},
		prompt.Choice{Name: "gRPC Service", Value: "grpc"},
	},
})
```

Key bindings in terminal mode: `up`/`k`, `down`/`j`, `enter` to confirm,
`ctrl+c`/`q` to abort.

---

### Checkbox

Multi-select list with toggle (bubbletea TUI in terminal mode).

```go
func Checkbox(cfg CheckboxConfig) ([]any, error)
```

```go
type CheckboxConfig struct {
	Message  string
	Choices  []ChoiceItem
	Default  []string
	PageSize int    // default: 10
	Loop     *bool  // default: true
	Validate func(any) error
	Filter   func(any) any
}
```

```go
features, err := prompt.Checkbox(prompt.CheckboxConfig{
	Message: "Features",
	Default: []string{"Docker support"},
	Choices: []prompt.ChoiceItem{
		prompt.Choice{Name: "Docker support", Value: "docker"},
		prompt.Choice{Name: "CI/CD", Value: "ci"},
		prompt.Choice{Name: "Load testing", Value: "load-test", Disabled: "coming soon"},
	},
})
```

Key bindings: `space` to toggle, `a` to toggle all, `enter` to confirm.

---

### Password

Masked text input. Uses `golang.org/x/term.ReadPassword` in terminal mode.

```go
func Password(cfg PasswordConfig) (string, error)
```

```go
type PasswordConfig struct {
	Message  string
	Mask     string // default: "*"
	Validate func(string) error
}
```

```go
pw, err := prompt.Password(prompt.PasswordConfig{
	Message: "API key",
})
```

---

### Number

Numeric input with optional min/max bounds.

```go
func Number(cfg NumberConfig) (float64, error)
```

```go
type NumberConfig struct {
	Message      string
	Default      *float64
	Min          *float64
	Max          *float64
	FloatAllowed bool
	Validate     func(float64) error
	Filter       func(float64) float64
}
```

```go
port := 8080.0
p, err := prompt.Number(prompt.NumberConfig{
	Message:      "Port",
	Default:      &port,
	Min:          floatPtr(1024),
	Max:          floatPtr(65535),
	FloatAllowed: false,
})

func floatPtr(v float64) *float64 { return &v }
```

---

### Editor

Opens `$VISUAL`, `$EDITOR`, or `vi` for multi-line text input.

```go
func Editor(cfg EditorConfig) (string, error)
```

```go
type EditorConfig struct {
	Message string
	Default string
	Postfix string // file extension, default: ".txt"
}
```

```go
body, err := prompt.Editor(prompt.EditorConfig{
	Message: "Commit message",
	Postfix: ".md",
})
```

---

### Search

Searchable selection with a dynamic source function.

```go
func Search(cfg SearchConfig) (any, error)
```

```go
type SearchConfig struct {
	Message  string
	Source   func(term string) []ChoiceItem // required
	PageSize int                            // default: 10
	Validate func(any) error
	Filter   func(any) any
}
```

```go
pkg, err := prompt.Search(prompt.SearchConfig{
	Message: "Package",
	Source: func(term string) []prompt.ChoiceItem {
		// Return filtered choices based on term
		return []prompt.ChoiceItem{
			prompt.Choice{Name: "fmt", Value: "fmt"},
			prompt.Choice{Name: "net/http", Value: "net/http"},
		}
	},
})
```

---

### Rawlist

Numbered list -- the user selects by typing a number.

```go
func Rawlist(cfg RawlistConfig) (any, error)
```

```go
type RawlistConfig struct {
	Message  string
	Choices  []ChoiceItem
	Validate func(any) error
	Filter   func(any) any
}
```

```go
env, err := prompt.Rawlist(prompt.RawlistConfig{
	Message: "Environment",
	Choices: []prompt.ChoiceItem{
		prompt.Choice{Name: "Development", Value: "dev"},
		prompt.Choice{Name: "Staging", Value: "staging"},
		prompt.Choice{Name: "Production", Value: "prod"},
	},
})
```

---

### Expand

Compact key-based selection. Each choice has a single-character key.

```go
func Expand(cfg ExpandConfig) (any, error)
```

```go
type ExpandChoice struct {
	Key   string
	Name  string
	Value any
}

type ExpandConfig struct {
	Message  string
	Choices  []ExpandChoice
	Validate func(any) error
	Filter   func(any) any
}
```

```go
action, err := prompt.Expand(prompt.ExpandConfig{
	Message: "Conflict on file.txt",
	Choices: []prompt.ExpandChoice{
		{Key: "y", Name: "Overwrite", Value: "overwrite"},
		{Key: "n", Name: "Skip", Value: "skip"},
		{Key: "d", Name: "Show diff", Value: "diff"},
	},
})
```

The user types `h` or `help` to see the full list.

---

### Path

File or directory path input.

```go
func Path(cfg PathConfig) (string, error)
```

```go
type PathConfig struct {
	Message         string
	Default         string
	OnlyDirectories bool
	Validate        func(string) error
}
```

```go
dir, err := prompt.Path(prompt.PathConfig{
	Message:         "Output directory",
	Default:         "./out",
	OnlyDirectories: true,
})
```

---

### Autocomplete

Text input with a suggestion list. Accepts any string, not only suggestions.

```go
func Autocomplete(cfg AutocompleteConfig) (string, error)
```

```go
type AutocompleteConfig struct {
	Message  string
	Choices  []string
	Default  string
	Validate func(string) error
}
```

```go
color, err := prompt.Autocomplete(prompt.AutocompleteConfig{
	Message: "Favorite color",
	Choices: []string{"red", "green", "blue", "yellow"},
})
```

## Choices

List-based prompts (Select, Checkbox, Search, Rawlist) accept a `[]ChoiceItem`
slice. `ChoiceItem` is a sealed interface implemented by `Choice` and
`Separator`.

```go
type Choice struct {
	Name        string `json:"name"`
	Value       any    `json:"value"`
	Disabled    any    `json:"disabled,omitempty"`    // nil/false = enabled, true or string = disabled
	Short       string `json:"short,omitempty"`
	Description string `json:"description,omitempty"`
}

type Separator struct {
	Text string `json:"text"` // defaults to "────────" when empty
}
```

Use `IsSelectable` to check whether a `ChoiceItem` is an enabled `Choice`:

```go
for _, item := range choices {
	if prompt.IsSelectable(item) {
		// item is a Choice that is not disabled
	}
}
```

Disabled choices appear grayed out in the TUI and cannot be selected. Set
`Disabled` to `true` for a generic disable, or to a string (e.g.
`"coming soon"`) to show a reason.

## Callbacks -- Validate and Filter

Most config structs accept `Validate` and `Filter` callbacks.

- **Filter** runs first and transforms the value before validation.
- **Validate** runs second. Return a non-nil error to reject the input. In
  terminal mode the prompt re-asks; in agent mode the error is returned
  immediately.

Callback signatures vary by prompt type:

| Prompt | Validate | Filter |
|---|---|---|
| Text | `func(string) error` | `func(string) string` |
| Confirm | `func(any) error` | `func(any) any` |
| Select | `func(any) error` | `func(any) any` |
| Checkbox | `func(any) error` | `func(any) any` |
| Password | `func(string) error` | -- |
| Number | `func(float64) error` | `func(float64) float64` |
| Search | `func(any) error` | `func(any) any` |
| Rawlist | `func(any) error` | `func(any) any` |
| Expand | `func(any) error` | `func(any) any` |
| Path | `func(string) error` | -- |
| Autocomplete | `func(string) error` | -- |
| Editor | -- | -- |

Example with both:

```go
name, err := prompt.Text(prompt.TextConfig{
	Message: "Username",
	Filter:  strings.ToLower,
	Validate: func(s string) error {
		if len(s) < 3 {
			return fmt.Errorf("must be at least 3 characters")
		}
		return nil
	},
})
```

## Agent Protocol

When `IsAgentMode()` returns true (non-TTY stdin, or `INQUIRER_AI_MODE=agent`),
every prompt communicates over a JSONL protocol on stdout/stdin instead of
rendering a terminal UI.

1. On the first prompt call the library emits a **handshake** line:

```json
{"protocol":"inquirer-ai","version":"0.1.0","format":"jsonl","interaction":"sequential","description":"...","example_response":{"answer":"<value>"}}
```

2. Each prompt emits a **question** JSON line on stdout:

```json
{"type":"select","message":"Template","choices":[{"name":"Web API","value":"web-api"},{"name":"CLI Tool","value":"cli-tool"}]}
```

3. The agent replies with a single JSON line on stdin:

```json
{"answer":"web-api"}
```

4. The next prompt emits the next question, and so on (sequential,
   one-at-a-time).

This is the same JSONL protocol used by the Python `inquirer-ai` package. See
[spec/protocol.md](../spec/protocol.md) for the full specification.

`IsAgentMode()` can be forced with the environment variable:

```sh
INQUIRER_AI_MODE=agent ./myapp   # force agent mode
INQUIRER_AI_MODE=human ./myapp   # force terminal mode
```

## Error Handling

All prompt functions return an error as the second value. The package defines
these sentinel errors (use `errors.Is` to check):

```go
var (
	ErrAborted       = errors.New("prompt aborted")       // user pressed Ctrl+C / q
	ErrValidation    = errors.New("validation failed")    // Validate callback rejected input
	ErrInvalidChoice = errors.New("invalid choice")       // answer not in choice list
	ErrInvalidJSON   = errors.New("invalid JSON response") // agent sent malformed JSON
	ErrStdinClosed   = errors.New("stdin closed")         // agent pipe closed
	ErrEditor        = errors.New("editor error")         // $EDITOR process failed
)
```

```go
result, err := prompt.Select(cfg)
if errors.Is(err, prompt.ErrAborted) {
	fmt.Println("User cancelled.")
	os.Exit(0)
}
if err != nil {
	log.Fatal(err)
}
```

## Theme

`DefaultTheme` controls the symbols used in prompt rendering. Override it at
program start to customize the look.

```go
type Theme struct {
	SymQuestion  string // prefix for the question line    (default "?")
	SymSuccess   string // prefix after successful answer  (default "✓")
	SymPointer   string // cursor indicator in lists       (default "❯")
	SymChecked   string // checked checkbox mark           (default "◉")
	SymUnchecked string // unchecked checkbox mark         (default "◯")
}
```

```go
prompt.DefaultTheme = prompt.Theme{
	SymQuestion:  ">",
	SymSuccess:   "[ok]",
	SymPointer:   "->",
	SymChecked:   "[x]",
	SymUnchecked: "[ ]",
}
```

## Terminal UI

Select and Checkbox prompts use [bubbletea](https://github.com/charmbracelet/bubbletea)
for a full-screen interactive TUI with cursor navigation and pagination. All
terminal styling (colors, bold) is handled by
[lipgloss](https://github.com/charmbracelet/lipgloss).

The TUI supports:

- **Pagination** -- long lists scroll with "(more above)" / "(more below)"
  indicators, controlled by `PageSize` (default 10).
- **Loop** -- when `Loop` is true (the default), the cursor wraps from last
  to first item and vice versa.
- **Disabled items** -- shown in muted style, cannot be selected.
- **Separators** -- rendered as divider lines between choice groups.

Style variables used internally:

| Variable | Purpose | Color |
|---|---|---|
| `styleQuestion` | Question prefix | `#9fa4e3` (lavender) |
| `styleSuccess` | Success prefix | `#62bfa1` (green) |
| `stylePointer` | Cursor arrow | `#9c99ec` (purple) |
| `styleHighlight` | Focused item text | `#90bbe9` (blue) |
| `styleSelected` | Checked items | `#59bca4` (teal) |
| `styleAnswer` | Confirmed answer | `#9db9dd` (light blue) |
| `styleError` | Validation errors | `#d77780` (red) |
| `styleMuted` | Hints, disabled items | `#84858f` (gray) |

Other prompts (Text, Confirm, Password, Number, Rawlist, Expand, Path,
Autocomplete) use simple line-based terminal I/O with the same lipgloss
styling and `DefaultTheme` symbols.

## License

See [LICENSE](./LICENSE).
