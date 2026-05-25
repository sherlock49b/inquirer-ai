package prompt

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

// ExpandChoice represents a single option in an expand prompt, identified by a key character.
type ExpandChoice struct {
	Key   string
	Name  string
	Value any
}

// ExpandConfig configures a compact key-based selection prompt.
type ExpandConfig struct {
	Message  string
	Choices  []ExpandChoice
	Validate func(any) error
	Filter   func(any) any
}

// Expand prompts the user to select by typing a single key character.
func Expand(cfg ExpandConfig) (any, error) {
	if len(cfg.Choices) == 0 {
		return nil, fmt.Errorf("%w: choices cannot be empty", ErrInvalidChoice)
	}
	seen := make(map[string]bool)
	for _, c := range cfg.Choices {
		k := strings.ToLower(c.Key)
		if seen[k] {
			return nil, fmt.Errorf("%w: duplicate expand key: %q", ErrInvalidChoice, k)
		}
		seen[k] = true
	}

	if IsAgentMode() {
		// expandAgent handles validation, filter, and retry internally
		return expandAgent(cfg)
	}
	result, err := expandTerminal(cfg)
	if err != nil {
		return nil, err
	}
	return applyCallbacks(result, cfg.Validate, cfg.Filter)
}

func expandAgent(cfg ExpandConfig) (any, error) {
	items := make([]map[string]any, len(cfg.Choices))
	for i, c := range cfg.Choices {
		items[i] = map[string]any{"key": strings.ToLower(c.Key), "name": c.Name, "value": c.Value}
	}
	payload := map[string]any{
		"type":    "expand",
		"message": cfg.Message,
		"choices": items,
	}
	return AgentPromptWithRetry(payload, func(answer any) (any, error) {
		s := toString(answer)
		lower := strings.ToLower(s)
		var matched any
		found := false
		for _, c := range cfg.Choices {
			if lower == strings.ToLower(c.Key) || s == toString(c.Value) || s == c.Name {
				matched = c.Value
				found = true
				break
			}
		}
		if !found {
			return nil, fmt.Errorf("%w: %q", ErrInvalidChoice, s)
		}
		return applyCallbacks(matched, cfg.Validate, cfg.Filter)
	})
}

type expandModel struct {
	message  string
	choices  []ExpandChoice
	hint     string
	expanded bool
	input    string
	done     bool
	aborted  bool
	result   any
	name     string
	errMsg   string
}

func (m expandModel) Init() tea.Cmd { return nil }

func (m expandModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	if keyMsg, ok := msg.(tea.KeyMsg); ok {
		switch keyMsg.String() {
		case "ctrl+c":
			m.aborted = true
			return m, tea.Quit
		case "h":
			m.expanded = !m.expanded
			m.errMsg = ""
			return m, nil
		case "enter":
			if m.input == "" {
				return m, nil
			}
			lower := strings.ToLower(m.input)
			for _, c := range m.choices {
				if lower == strings.ToLower(c.Key) {
					m.result = c.Value
					m.name = c.Name
					m.done = true
					return m, tea.Quit
				}
			}
			m.errMsg = "Invalid key. Press h for help."
			m.input = ""
			return m, nil
		case "backspace":
			if len(m.input) > 0 {
				m.input = m.input[:len(m.input)-1]
			}
			m.errMsg = ""
			return m, nil
		default:
			s := keyMsg.String()
			if len(s) == 1 {
				m.input = s
				m.errMsg = ""
			}
			return m, nil
		}
	}
	return m, nil
}

func (m expandModel) View() string {
	if m.done || m.aborted {
		return ""
	}

	var b strings.Builder
	b.WriteString(renderQuestion(m.message))

	if m.expanded {
		b.WriteString("\n")
		for _, c := range m.choices {
			b.WriteString(fmt.Sprintf("  %s) %s\n", strings.ToLower(c.Key), c.Name))
		}
		b.WriteString(styleMuted.Render("  (h to collapse)") + "\n")
	} else {
		b.WriteString(" " + styleMuted.Render("("+m.hint+")") + "\n")
	}

	if m.errMsg != "" {
		b.WriteString(renderError(m.errMsg) + "\n")
	}

	b.WriteString("  > " + m.input)

	return b.String()
}

func expandTerminal(cfg ExpandConfig) (any, error) {
	keys := make([]string, len(cfg.Choices))
	for i, c := range cfg.Choices {
		keys[i] = strings.ToLower(c.Key)
	}
	hasH := false
	for _, k := range keys {
		if k == "h" {
			hasH = true
			break
		}
	}
	if !hasH {
		keys = append(keys, "h")
	}
	hint := strings.Join(keys, "/")

	m := expandModel{
		message: cfg.Message,
		choices: cfg.Choices,
		hint:    hint,
	}

	p := tea.NewProgram(m)
	finalModel, err := p.Run()
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrAborted, err)
	}

	final := finalModel.(expandModel)
	if final.aborted {
		return nil, ErrAborted
	}

	fmt.Println(renderSuccess(cfg.Message, final.name))
	return final.result, nil
}
