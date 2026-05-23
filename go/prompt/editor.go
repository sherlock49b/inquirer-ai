package prompt

import (
	"fmt"
	"os"
	"os/exec"
)

type EditorConfig struct {
	Message string
	Default string
	Postfix string
}

func Editor(cfg EditorConfig) (string, error) {
	if cfg.Postfix == "" {
		cfg.Postfix = ".txt"
	}
	if IsAgentMode() {
		return editorAgent(cfg)
	}
	return editorTerminal(cfg)
}

func editorAgent(cfg EditorConfig) (string, error) {
	payload := map[string]any{
		"type":    "editor",
		"message": cfg.Message,
		"default": nilIfEmpty(cfg.Default),
		"postfix": cfg.Postfix,
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
	return result, nil
}

func editorTerminal(cfg EditorConfig) (string, error) {
	editor := os.Getenv("VISUAL")
	if editor == "" {
		editor = os.Getenv("EDITOR")
	}
	if editor == "" {
		editor = "vi"
	}

	f, err := os.CreateTemp("", "inquirer-*"+cfg.Postfix)
	if err != nil {
		return "", fmt.Errorf("failed to create temp file: %w", err)
	}
	tmpPath := f.Name()
	defer os.Remove(tmpPath)

	if cfg.Default != "" {
		f.WriteString(cfg.Default)
	}
	f.Close()

	cmd := exec.Command(editor, tmpPath)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("editor failed: %w", err)
	}

	data, err := os.ReadFile(tmpPath)
	if err != nil {
		return "", fmt.Errorf("failed to read edited file: %w", err)
	}

	t := DefaultTheme
	fmt.Printf("%s %s (editor)\n", t.SymSuccess, cfg.Message)
	return string(data), nil
}
