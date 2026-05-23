package prompt

import (
	"fmt"
)

// SearchConfig configures a searchable selection prompt with a dynamic source.
type SearchConfig struct {
	Message  string
	Source   func(term string) []ChoiceItem
	PageSize int
	Validate func(any) error
	Filter   func(any) any
}

// Search prompts the user to select from a dynamically filtered list.
func Search(cfg SearchConfig) (any, error) {
	if cfg.PageSize == 0 {
		cfg.PageSize = 10
	}
	if cfg.Source == nil {
		return nil, fmt.Errorf("%w: source function is required", ErrValidation)
	}
	if IsAgentMode() {
		// searchAgent handles validation, filter, and retry internally
		return searchAgent(cfg)
	}
	result, err := searchTerminal(cfg)
	if err != nil {
		return nil, err
	}
	return applyCallbacks(result, cfg.Validate, cfg.Filter)
}

func searchAgent(cfg SearchConfig) (any, error) {
	items := cfg.Source("")
	initial := parseChoices(items)
	payload := map[string]any{
		"type":       "search",
		"message":    cfg.Message,
		"searchable": true,
		"choices":    marshalItems(items),
	}
	return AgentPromptWithRetry(payload, func(answer any) (any, error) {
		s := toString(answer)
		var matched any
		for _, c := range initial {
			if c.selectable && (s == toString(c.value) || s == c.name) {
				matched = c.value
				break
			}
		}
		if matched == nil {
			matched = s
		}
		return applyCallbacks(matched, cfg.Validate, cfg.Filter)
	})
}

func searchTerminal(cfg SearchConfig) (any, error) {
	t := DefaultTheme
	choices := parseChoices(cfg.Source(""))
	selectable := selectableIndices(choices)
	if len(selectable) == 0 {
		return nil, fmt.Errorf("%w: no choices returned", ErrInvalidChoice)
	}
	cursor := selectable[0]

	for {
		fmt.Printf("\033[2J\033[H")
		fmt.Printf("%s %s (type to search)\n", t.SymQuestion, cfg.Message)
		end := len(choices)
		if end > cfg.PageSize {
			end = cfg.PageSize
		}
		for i := 0; i < end; i++ {
			c := choices[i]
			if c.isSeparator {
				fmt.Printf("  %s\n", c.name)
				continue
			}
			if !c.selectable {
				continue
			}
			if i == cursor {
				fmt.Printf("%s %s\n", t.SymPointer, c.name)
			} else {
				fmt.Printf("  %s\n", c.name)
			}
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
			if cursor < len(choices) {
				c := choices[cursor]
				fmt.Printf("\033[2J\033[H%s %s %s\n", t.SymSuccess, cfg.Message, c.name)
				return c.value, nil
			}
			return nil, ErrAborted
		case keyCtrlC:
			return nil, ErrAborted
		}
	}
}
