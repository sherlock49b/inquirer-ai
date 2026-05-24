package prompt

import "fmt"

// CheckboxConfig configures a multi-select checkbox prompt.
type CheckboxConfig struct {
	Message  string
	Choices  []ChoiceItem
	Default  []string
	PageSize int
	Loop     *bool
	Validate func(any) error
	Filter   func(any) any
}

// Checkbox prompts the user to select multiple items from a list.
func Checkbox(cfg CheckboxConfig) ([]any, error) {
	if cfg.PageSize == 0 {
		cfg.PageSize = 10
	}
	if cfg.Loop == nil {
		t := true
		cfg.Loop = &t
	}
	choices := parseChoices(cfg.Choices)
	if len(choices) == 0 {
		return nil, fmt.Errorf("%w: choices cannot be empty", ErrInvalidChoice)
	}
	if len(selectableIndices(choices)) == 0 {
		return nil, fmt.Errorf("%w: no selectable choices", ErrInvalidChoice)
	}
	if IsAgentMode() {
		// checkboxAgent handles validation, filter, and retry internally
		return checkboxAgent(cfg, choices)
	}
	result, err := checkboxTerminal(cfg, choices)
	if err != nil {
		return nil, err
	}
	return applyCallbacksList(result, cfg.Validate, cfg.Filter)
}

func checkboxAgent(cfg CheckboxConfig, choices []resolvedChoice) ([]any, error) {
	payload := map[string]any{
		"type":    "checkbox",
		"message": cfg.Message,
		"default": cfg.Default,
		"choices": marshalItems(cfg.Choices),
	}
	raw, err := AgentPromptWithRetry(payload, func(answer any) (any, error) {
		list, ok := answer.([]any)
		if !ok {
			return nil, fmt.Errorf("%w: expected a list", ErrValidation)
		}

		var result []any
		for _, v := range list {
			s := toString(v)
			found := false
			for _, c := range choices {
				if !c.selectable {
					continue
				}
				if s == toString(c.value) || s == c.name {
					result = append(result, c.value)
					found = true
					break
				}
			}
			if !found {
				return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, s)
			}
		}
		return applyCallbacksList(result, cfg.Validate, cfg.Filter)
	})
	if err != nil {
		return nil, err
	}
	val, ok := raw.([]any)
	if !ok {
		return nil, fmt.Errorf("%w: expected []any, got %T", ErrValidation, raw)
	}
	return val, nil
}

func checkboxTerminal(cfg CheckboxConfig, choices []resolvedChoice) ([]any, error) {
	return runCheckboxTUI(cfg, choices)
}
