package prompt

import (
	"os"
	"strings"

	"golang.org/x/term"
)

// IsAgentMode returns true when prompts should use the JSON line protocol
// instead of interactive terminal UI. Determined by INQUIRER_AI_MODE env var
// or whether stdin is a TTY.
func IsAgentMode() bool {
	env := strings.ToLower(os.Getenv("INQUIRER_AI_MODE"))
	if env == "agent" {
		return true
	}
	if env == "human" {
		return false
	}
	return !term.IsTerminal(int(os.Stdin.Fd()))
}
