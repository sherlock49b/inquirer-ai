package prompt

import (
	"os"
	"strings"

	"golang.org/x/term"
)

// IsAgentMode returns true when prompts should use the JSON line protocol
// instead of the interactive terminal UI.
//
// Per the parity contract (R3):
//
//	is_human        = INQUIRER_AI_MODE == "human" (case-insensitive)
//	socket_requested = INQUIRER_AI_SOCKET set & non-empty, OR MODE == "agent"
//	is_agent        = (not is_human) AND (socket_requested OR stdin-not-a-TTY)
//
// Crucially, setting INQUIRER_AI_SOCKET activates agent mode even on a TTY.
func IsAgentMode() bool {
	env := strings.ToLower(os.Getenv("INQUIRER_AI_MODE"))
	if env == "human" {
		return false
	}
	if socketRequested() {
		return true
	}
	return !term.IsTerminal(int(os.Stdin.Fd()))
}

// socketRequested reports whether a socket transport is explicitly requested:
// INQUIRER_AI_SOCKET set & non-empty, OR INQUIRER_AI_MODE == "agent".
func socketRequested() bool {
	if os.Getenv("INQUIRER_AI_SOCKET") != "" {
		return true
	}
	return strings.ToLower(os.Getenv("INQUIRER_AI_MODE")) == "agent"
}
