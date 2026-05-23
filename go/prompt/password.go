package prompt

import (
	"fmt"
	"os"
	"strings"

	"golang.org/x/term"
)

type PasswordConfig struct {
	Message  string
	Mask     string
	Validate func(string) error
}

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
			return "", fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
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
