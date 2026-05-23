package prompt

import (
	"os"
	"strings"

	"golang.org/x/term"
)

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
