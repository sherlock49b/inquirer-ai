package prompt

import (
	"fmt"
	"os"
	"os/exec"
)

// EditorConfig configures an editor-based text input prompt.
type EditorConfig struct {
	Message string
	Default string
	Postfix string
}

// Editor opens the user's preferred editor ($VISUAL or $EDITOR) for multi-line text input.
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
	// Route through the shared agent helper so the socket transport is used
	// when active and the handshake/step counter is not desynced. Editor has
	// no validate callback, so the closure only applies the default-on-nil rule.
	raw, err := AgentPromptWithRetry(payload, func(answer any) (any, error) {
		return resolveStringDefault(answer, cfg.Default), nil
	})
	if err != nil {
		return "", err
	}
	val, ok := raw.(string)
	if !ok {
		return "", fmt.Errorf("%w: expected string, got %T", ErrValidation, raw)
	}
	return val, nil
}

func editorTerminal(cfg EditorConfig) (string, error) {
	editor := os.Getenv("VISUAL")
	if editor == "" {
		editor = os.Getenv("EDITOR")
	}
	if editor == "" {
		editor = "vi"
	}

	// Parse the editor command with quote-aware shell-word splitting so values
	// like `code --wait` or `"/path with spaces/ed" -n` work, then exec argv
	// WITHOUT a shell (no injection).
	argv, err := splitShellWords(editor)
	if err != nil {
		return "", fmt.Errorf("%w: invalid editor command %q: %v", ErrEditor, editor, err)
	}
	if len(argv) == 0 {
		return "", fmt.Errorf("%w: empty editor command", ErrEditor)
	}

	// os.CreateTemp creates a randomized name with O_EXCL and mode 0600.
	f, err := os.CreateTemp("", "inquirer-*"+cfg.Postfix)
	if err != nil {
		return "", fmt.Errorf("failed to create temp file: %w", err)
	}
	tmpPath := f.Name()
	defer func() { _ = os.Remove(tmpPath) }() // removed on EVERY exit path

	if cfg.Default != "" {
		if _, werr := f.WriteString(cfg.Default); werr != nil {
			_ = f.Close()
			return "", fmt.Errorf("failed to write temp file: %w", werr)
		}
	}
	_ = f.Close()

	args := make([]string, 0, len(argv))
	args = append(args, argv[1:]...)
	args = append(args, tmpPath)
	cmd := exec.Command(argv[0], args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("%w: %v", ErrEditor, err)
	}

	data, err := os.ReadFile(tmpPath)
	if err != nil {
		return "", fmt.Errorf("failed to read edited file: %w", err)
	}

	t := DefaultTheme
	fmt.Printf("%s %s (editor)\n", t.SymSuccess, cfg.Message)
	return string(data), nil
}

// splitShellWords splits a command string into argv using POSIX-style
// quote-aware rules: whitespace separates words, single quotes preserve their
// contents literally, double quotes preserve contents allowing backslash
// escapes of \", \\, and a backslash outside quotes escapes the next rune.
// It returns an error on an unterminated quote.
func splitShellWords(s string) ([]string, error) {
	var (
		args    []string
		cur     []rune
		inWord  bool
		inS     bool // inside single quotes
		inD     bool // inside double quotes
		escaped bool
	)
	flush := func() {
		if inWord {
			args = append(args, string(cur))
			cur = cur[:0]
			inWord = false
		}
	}
	for _, r := range s {
		switch {
		case escaped:
			cur = append(cur, r)
			escaped = false
			inWord = true
		case inS:
			if r == '\'' {
				inS = false
			} else {
				cur = append(cur, r)
			}
		case inD:
			switch r {
			case '\\':
				escaped = true
			case '"':
				inD = false
			default:
				cur = append(cur, r)
			}
		case r == '\\':
			escaped = true
			inWord = true
		case r == '\'':
			inS = true
			inWord = true
		case r == '"':
			inD = true
			inWord = true
		case r == ' ' || r == '\t' || r == '\n' || r == '\r':
			flush()
		default:
			cur = append(cur, r)
			inWord = true
		}
	}
	if inS || inD {
		return nil, fmt.Errorf("unterminated quote")
	}
	if escaped {
		return nil, fmt.Errorf("trailing backslash")
	}
	flush()
	return args, nil
}
