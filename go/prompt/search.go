package prompt

import (
	"fmt"
)

// SearchConfig configures a searchable selection prompt with a dynamic source.
//
// The Source function is called asynchronously: each invocation runs in its own
// goroutine via bubbletea's Cmd pattern, so it may safely perform blocking I/O
// (HTTP requests, database queries, file-system walks, etc.) without freezing
// the terminal UI.  Keystrokes are debounced so that a slow source is not
// hammered on every character while the user is still typing.
//
// Because Go's concurrency model lets the caller do async work inside a
// sync-looking function (e.g. using goroutines and channels internally), the
// Source signature remains a plain func(string) []ChoiceItem.
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
		"default":    nil,
		"searchable": true,
		"choices":    marshalItems(items),
	}
	return AgentPromptWithRetry(payload, func(answer any) (any, error) {
		// If the answer matches an advertised choice (type-aware value match
		// OR exact name match) return that choice's value; otherwise return
		// the answer verbatim as a string (dynamic-source-safe).
		var matched any = toString(answer)
		for _, c := range initial {
			if c.selectable && matchesChoice(answer, c) {
				matched = c.value
				break
			}
		}
		return applyCallbacks(matched, cfg.Validate, cfg.Filter)
	})
}

func searchTerminal(cfg SearchConfig) (any, error) {
	return runSearchTUI(cfg)
}
