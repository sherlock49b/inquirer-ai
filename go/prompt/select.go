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
}

// Select prompts the user to pick one item from a list.
func Select(cfg SelectConfig) (any, error) {
	if cfg.PageSize == 0 {
		cfg.PageSize = 10
	}
	choices := parseChoices(cfg.Choices)
	if len(choices) == 0 {
		return nil, fmt.Errorf("%w: choices cannot be empty", ErrInvalidChoice)
	}
	if IsAgentMode() {
		return selectAgent(cfg, choices)
	}
	return selectTerminal(cfg, choices)
}

func selectAgent(cfg SelectConfig, choices []resolvedChoice) (any, error) {
	payload := map[string]any{
		"type":    "select",
		"message": cfg.Message,
		"default": nilIfEmpty(cfg.Default),
		"choices": marshalItems(cfg.Choices),
	}
	if err := AgentSend(payload); err != nil {
		return nil, err
	}

	answer, err := AgentReceive()
	if err != nil {
		return nil, err
	}

	answerStr := toString(answer)
	for _, c := range choices {
		if !c.selectable {
			continue
		}
		if answerStr == toString(c.value) || answerStr == c.name {
			return c.value, nil
		}
	}
	return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, answerStr)
}

func selectTerminal(cfg SelectConfig, choices []resolvedChoice) (any, error) {
	t := DefaultTheme
	selectable := selectableIndices(choices)
	if len(selectable) == 0 {
		return nil, fmt.Errorf("%w: no selectable choices", ErrInvalidChoice)
	}

	cursor := selectable[0]
	if cfg.Default != "" {
		for _, idx := range selectable {
			c := choices[idx]
			if toString(c.value) == cfg.Default || c.name == cfg.Default {
				cursor = idx
				break
			}
		}
	}

	for {
		fmt.Printf("\033[2J\033[H")
		fmt.Printf("%s %s\n", t.SymQuestion, cfg.Message)
		start, end := visibleRange(cursor, len(choices), cfg.PageSize)
		if start > 0 {
			fmt.Println("  (more above)")
		}
		for i := start; i < end; i++ {
			c := choices[i]
			if c.isSeparator {
				fmt.Printf("  %s\n", c.name)
				continue
			}
			if !c.selectable {
				fmt.Printf("  %s (disabled)\n", c.name)
				continue
			}
			if i == cursor {
				fmt.Printf("%s %s\n", t.SymPointer, c.name)
			} else {
				fmt.Printf("  %s\n", c.name)
			}
		}
		if end < len(choices) {
			fmt.Println("  (more below)")
		}

		key, err := readKey()
		if err != nil {
			return nil, ErrAborted
		}
		switch key {
		case keyUp:
			cursor = moveCursor(cursor, -1, selectable, true)
		case keyDown:
			cursor = moveCursor(cursor, 1, selectable, true)
		case keyEnter:
			c := choices[cursor]
			fmt.Printf("\033[2J\033[H%s %s %s\n", t.SymSuccess, cfg.Message, c.name)
			return c.value, nil
		case keyCtrlC:
			return nil, ErrAborted
		}
	}
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
