package prompt

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

type selectModel struct {
	message    string
	choices    []resolvedChoice
	selectable []int
	cursor     int
	pageSize   int
	loop       bool
	done       bool
	aborted    bool
}

func (m selectModel) Init() tea.Cmd { return nil }

func (m selectModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	if keyMsg, ok := msg.(tea.KeyMsg); ok {
		switch keyMsg.String() {
		case "up", "k":
			m.cursor = moveCursor(m.cursor, -1, m.selectable, m.loop)
		case "down", "j":
			m.cursor = moveCursor(m.cursor, 1, m.selectable, m.loop)
		case "1", "2", "3", "4", "5", "6", "7", "8", "9":
			n := int(keyMsg.String()[0] - '0') // 1-based index
			if n > len(m.selectable) {
				n = len(m.selectable)
			}
			m.cursor = m.selectable[n-1]
		case "enter":
			m.done = true
			return m, tea.Quit
		case "ctrl+c":
			m.aborted = true
			return m, tea.Quit
		}
	}
	return m, nil
}

func (m selectModel) View() string {
	if m.done || m.aborted {
		return ""
	}

	var b strings.Builder
	b.WriteString(renderQuestion(m.message) + "\n")

	start, end := visibleRange(m.cursor, len(m.choices), m.pageSize)
	if start > 0 {
		b.WriteString(styleMuted.Render("  (more above)") + "\n")
	}
	for i := start; i < end; i++ {
		c := m.choices[i]
		if c.isSeparator {
			b.WriteString(styleMuted.Render("  "+c.name) + "\n")
			continue
		}
		if !c.selectable {
			reason := " (disabled)"
			b.WriteString(styleMuted.Render("  "+c.name+reason) + "\n")
			continue
		}
		if i == m.cursor {
			desc := ""
			b.WriteString(stylePointer.Render(DefaultTheme.SymPointer) + " " + styleHighlight.Render(c.name) + desc + "\n")
		} else {
			b.WriteString("  " + c.name + "\n")
		}
	}
	if end < len(m.choices) {
		b.WriteString(styleMuted.Render("  (more below)") + "\n")
	}

	return b.String()
}

func runSelectTUI(cfg SelectConfig, choices []resolvedChoice) (any, error) {
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

	m := selectModel{
		message:    cfg.Message,
		choices:    choices,
		selectable: selectable,
		cursor:     cursor,
		pageSize:   cfg.PageSize,
		loop:       *cfg.Loop,
	}

	p := tea.NewProgram(m)
	finalModel, err := p.Run()
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrAborted, err)
	}

	final := finalModel.(selectModel)
	if final.aborted {
		return nil, ErrAborted
	}

	c := choices[final.cursor]
	fmt.Println(renderSuccess(cfg.Message, c.name))
	return c.value, nil
}
