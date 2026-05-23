// Package prompt provides interactive CLI prompts for both humans and AI agents.
//
// In terminal mode (default when stdin is a TTY), prompts render an interactive
// UI with cursor navigation, key bindings, and styled output.
//
// In agent mode (non-TTY stdin or INQUIRER_AI_MODE=agent), prompts communicate
// via a JSON line protocol on stdout/stdin, enabling AI agents to drive CLI
// tools programmatically.
//
// Supported prompt types: Text, Confirm, Select, Checkbox, Password, Number,
// Editor, Search, Rawlist, Expand, Path, and Autocomplete.
package prompt
