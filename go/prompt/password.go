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
	const maxRetries = 3
	for attempt := 0; attempt < maxRetries; attempt++ {
		payload := map[string]any{
			"type":    "password",
			"message": cfg.Message,
			"mask":    cfg.Mask,
		}
		if err := AgentSend(payload); err != nil {
			return "", err
		}
		answer, err := AgentReceive()
		if err != nil {
			return "", err
		}
		result := toString(answer)
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				valErr := fmt.Errorf("%w: %v", ErrValidation, err)
				if attempt < maxRetries-1 {
					AgentSendValidationError(valErr.Error())
					continue
				}
				return "", valErr
			}
		}
		return result, nil
	}
	return "", fmt.Errorf("%w: max retries exceeded", ErrValidation)
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
