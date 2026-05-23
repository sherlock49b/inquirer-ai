package prompt

import (
	"fmt"
	"os"
	"path/filepath"
)

// PathConfig configures a file/directory path input prompt.
type PathConfig struct {
	Message         string
	Default         string
	OnlyDirectories bool
	Validate        func(string) error
}

// Path prompts for a file or directory path.
func Path(cfg PathConfig) (string, error) {
	if IsAgentMode() {
		return pathAgent(cfg)
	}
	return pathTerminal(cfg)
}

func pathAgent(cfg PathConfig) (string, error) {
	payload := map[string]any{
		"type":             "path",
		"message":          cfg.Message,
		"default":          nilIfEmpty(cfg.Default),
		"only_directories": cfg.OnlyDirectories,
	}
	if err := AgentSend(payload); err != nil {
		return "", err
	}
	answer, err := AgentReceive()
	if err != nil {
		return "", err
	}
	result := toString(answer)
	if result == "" && cfg.Default != "" {
		result = cfg.Default
	}
	if cfg.Validate != nil {
		if err := cfg.Validate(result); err != nil {
			return "", fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
}

func pathTerminal(cfg PathConfig) (string, error) {
	t := DefaultTheme
	scanner := getTerminalScanner()
	for {
		suffix := ""
		if cfg.Default != "" {
			suffix = fmt.Sprintf(" (%s)", cfg.Default)
		}
		fmt.Printf("%s %s%s: ", t.SymQuestion, cfg.Message, suffix)
		if !scanner.Scan() {
			return "", ErrAborted
		}
		result := scanner.Text()
		if result == "" && cfg.Default != "" {
			result = cfg.Default
		}

		if cfg.OnlyDirectories {
			info, err := os.Stat(result)
			if err != nil || !info.IsDir() {
				fmt.Printf("  Not a valid directory: %s\n", result)
				continue
			}
		}

		result = filepath.Clean(result)
		if cfg.Validate != nil {
			if err := cfg.Validate(result); err != nil {
				fmt.Printf("  %s\n", err)
				continue
			}
		}
		fmt.Printf("%s %s %s\n", t.SymSuccess, cfg.Message, result)
		return result, nil
	}
}
