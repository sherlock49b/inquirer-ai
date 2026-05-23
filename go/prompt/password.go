package prompt

import (
	"fmt"
	"os"
	"strings"

	"golang.org/x/term"
)

// PasswordConfig configures a masked password input prompt.
type PasswordConfig struct {
	Message  string
	Mask     string
	Validate func(string) error
}

// Password prompts for sensitive text input with masked display.
func Password(cfg PasswordConfig) (string, error) {
	if cfg.Mask == "" {
		cfg.Mask = "*"
	}
	if IsAgentMode() {
		return passwordAgent(cfg)
	}
	return passwordTerminal(cfg)
}

func passwordAgent(cfg PasswordConfig) (string, error) {
	payload := map[string]any{
		"type":    "password",
		"message": cfg.Message,
		"mask":    cfg.Mask,
	}
	raw, err := AgentPromptWithRetry(payload, func(answer any) (any, error) {
		result := toString(answer)
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				return nil, fmt.Errorf("%w: %v", ErrValidation, err)
			}
		}
		return result, nil
	})
	if err != nil {
		return "", err
	}
	return raw.(string), nil
}

func passwordTerminal(cfg PasswordConfig) (string, error) {
	t := DefaultTheme
	for {
		fmt.Printf("%s %s: ", t.SymQuestion, cfg.Message)
		pw, err := term.ReadPassword(int(os.Stdin.Fd()))
		fmt.Println()
		if err != nil {
			return "", ErrAborted
		}
		result := string(pw)
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				fmt.Printf("  %s\n", err)
				continue
			}
		}
		masked := strings.Repeat(cfg.Mask, len(result))
		fmt.Printf("%s %s %s\n", t.SymSuccess, cfg.Message, masked)
		return result, nil
	}
}
