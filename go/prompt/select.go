package prompt

import (
	"fmt"
)

// SelectConfig configures a single-choice selection prompt.
type SelectConfig struct {
	Message  string
	Choices  []ChoiceItem
	Default  string
	PageSize int
	Loop     *bool
	Validate func(any) error
	Filter   func(any) any
}

// Select prompts the user to pick one item from a list.
func Select(cfg SelectConfig) (any, error) {
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
		// selectAgent handles validation, filter, and retry internally
		return selectAgent(cfg, choices)
	}
	result, err := selectTerminal(cfg, choices)
	if err != nil {
		return nil, err
	}
	return applyCallbacks(result, cfg.Validate, cfg.Filter)
}

func selectAgent(cfg SelectConfig, choices []resolvedChoice) (any, error) {
	payload := map[string]any{
		"type":    "select",
		"message": cfg.Message,
		"default": nilIfEmpty(cfg.Default),
		"choices": marshalItems(cfg.Choices),
	}
	return AgentPromptWithRetry(payload, func(answer any) (any, error) {
		answerStr := toString(answer)
		var matched any
		found := false
		for _, c := range choices {
			if !c.selectable {
				continue
			}
			if answerStr == toString(c.value) || answerStr == c.name {
				matched = c.value
				found = true
				break
			}
		}
		if !found {
			return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, answerStr)
		}
		return applyCallbacks(matched, cfg.Validate, cfg.Filter)
	})
}

func selectTerminal(cfg SelectConfig, choices []resolvedChoice) (any, error) {
	return runSelectTUI(cfg, choices)
}

type resolvedChoice struct {
	name        string
	value       any
	selectable  bool
	isSeparator bool
}

func parseChoices(items []ChoiceItem) []resolvedChoice {
	var result []resolvedChoice
	for _, item := range items {
		switch v := item.(type) {
		case Choice:
			result = append(result, resolvedChoice{
				name:       v.Name,
				value:      v.Value,
				selectable: IsSelectable(v),
			})
		case Separator:
			text := v.Text
			if text == "" {
				text = "────────"
			}
			result = append(result, resolvedChoice{
				name:        text,
				isSeparator: true,
			})
		}
	}
	return result
}

func marshalItems(items []ChoiceItem) []any {
	var result []any
	for _, item := range items {
		switch v := item.(type) {
		case Choice:
			m := map[string]any{"name": v.Name, "value": v.Value}
			if v.Disabled != nil && v.Disabled != false {
				m["disabled"] = v.Disabled
			}
			if v.Short != "" {
				m["short"] = v.Short
			}
			if v.Description != "" {
				m["description"] = v.Description
			}
			result = append(result, m)
		case Separator:
			text := v.Text
			if text == "" {
				text = "────────"
			}
			result = append(result, map[string]any{"type": "separator", "text": text})
		}
	}
	return result
}

func selectableIndices(choices []resolvedChoice) []int {
	var indices []int
	for i, c := range choices {
		if c.selectable {
			indices = append(indices, i)
		}
	}
	return indices
}

func moveCursor(current, direction int, selectable []int, loop bool) int {
	pos := -1
	for i, idx := range selectable {
		if idx == current {
			pos = i
			break
		}
	}
	if pos == -1 {
		return selectable[0]
	}
	newPos := pos + direction
	if loop {
		newPos = ((newPos % len(selectable)) + len(selectable)) % len(selectable)
	} else {
		if newPos < 0 {
			newPos = 0
		}
		if newPos >= len(selectable) {
			newPos = len(selectable) - 1
		}
	}
	return selectable[newPos]
}

func visibleRange(cursor, total, pageSize int) (int, int) {
	ps := pageSize
	if ps > total {
		ps = total
	}
	start := cursor - ps/2
	if start < 0 {
		start = 0
	}
	if start > total-ps {
		start = total - ps
	}
	return start, start + ps
}
