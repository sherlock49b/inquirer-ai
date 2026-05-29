package prompt

import "fmt"

// TextConfig configures a free-text input prompt.
type TextConfig struct {
	Message   string
	Default   string
	KeepInput *bool
	Validate  func(string) error
	Filter    func(string) string
}

// Text prompts for a single line of text input.
func Text(cfg TextConfig) (string, error) {
	if IsAgentMode() {
		return textAgent(cfg)
	}
	return textTerminal(cfg)
}

func textAgent(cfg TextConfig) (string, error) {
	payload := map[string]any{
		"type":    "input",
		"message": cfg.Message,
		"default": nilIfEmpty(cfg.Default),
	}
	raw, err := AgentPromptWithRetry(payload, func(answer any) (any, error) {
		result := resolveStringDefault(answer, cfg.Default)
		return applyTextCallbacks(result, cfg)
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

func textKeepInput(cfg TextConfig) bool {
	if cfg.KeepInput != nil {
		return *cfg.KeepInput
	}
	return true // default true
}

func textTerminal(cfg TextConfig) (string, error) {
	scanner := getTerminalScanner()
	keepInput := textKeepInput(cfg)
	for {
		suffix := ""
		if cfg.Default != "" {
			suffix = styleMuted.Render(fmt.Sprintf(" (%s)", cfg.Default))
		}
		fmt.Printf("%s%s: ", renderQuestion(cfg.Message), suffix)

		if !scanner.Scan() {
			return "", ErrAborted
		}
		result := scanner.Text()
		if result == "" && cfg.Default != "" {
			result = cfg.Default
		}

		final, err := applyTextCallbacks(result, cfg)
		if err != nil {
			fmt.Println(renderError(err.Error()))
			if keepInput {
				cfg.Default = result
			}
			continue
		}
		fmt.Println(renderSuccess(cfg.Message, final))
		return final, nil
	}
}

func applyTextCallbacks(result string, cfg TextConfig) (string, error) {
	if cfg.Validate != nil {
		if err := cfg.Validate(result); err != nil {
			return "", fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	if cfg.Filter != nil {
		result = cfg.Filter(result)
	}
	return result, nil
}

func toString(v any) string {
	if v == nil {
		return ""
	}
	return fmt.Sprintf("%v", v)
}

// resolveStringDefault applies the default ONLY when the raw answer is nil
// (absent). An explicit empty string answer is returned verbatim as "".
func resolveStringDefault(answer any, def string) string {
	if answer == nil {
		return def
	}
	return toString(answer)
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}
