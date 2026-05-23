package prompt

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

type checkboxModel struct {
	message    string
	choices    []resolvedChoice
	selectable []int
	cursor     int
	checked    map[int]bool
	pageSize   int
	loop       bool
	done       bool
	aborted    bool
}

func (m checkboxModel) Init() tea.Cmd { return nil }

func (m checkboxModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	if keyMsg, ok := msg.(tea.KeyMsg); ok {
		switch keyMsg.String() {
		case "up", "k":
			m.cursor = moveCursor(m.cursor, -1, m.selectable, m.loop)
		case "down", "j":
			m.cursor = moveCursor(m.cursor, 1, m.selectable, m.loop)
		case " ":
			m.checked[m.cursor] = !m.checked[m.cursor]
		case "a":
			if len(m.checked) == len(m.selectable) {
				m.checked = make(map[int]bool)
			} else {
				for _, idx := range m.selectable {
					m.checked[idx] = true
				}
			}
		case "enter":
			m.done = true
			return m, tea.Quit
		case "ctrl+c", "q":
			m.aborted = true
			return m, tea.Quit
		}
	}
	return m, nil
}

func (m checkboxModel) View() string {
	if m.done || m.aborted {
		return ""
	}

	t := DefaultTheme
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
			b.WriteString(styleMuted.Render("  "+t.SymUnchecked+" "+c.name+" (disabled)") + "\n")
			continue
		}
		arrow := " "
		if i == m.cursor {
			arrow = stylePointer.Render(t.SymPointer)
		}
		mark := t.SymUnchecked
		if m.checked[i] {
			mark = t.SymChecked
		}
		if i == m.cursor {
			b.WriteString(arrow + " " + styleHighlight.Render(mark+" "+c.name) + "\n")
		} else if m.checked[i] {
			b.WriteString(arrow + " " + styleSelected.Render(mark+" "+c.name) + "\n")
		} else {
			b.WriteString(arrow + " " + mark + " " + c.name + "\n")
		}
	}
	if end < len(m.choices) {
		b.WriteString(styleMuted.Render("  (more below)") + "\n")
	}

	return b.String()
}

func runCheckboxTUI(cfg CheckboxConfig, choices []resolvedChoice) ([]any, error) {
	selectable := selectableIndices(choices)
	if len(selectable) == 0 {
		return nil, fmt.Errorf("%w: no selectable choices", ErrInvalidChoice)
	}

	checked := make(map[int]bool)
	for _, idx := range selectable {
		for _, d := range cfg.Default {
			c := choices[idx]
			if c.name == d || toString(c.value) == d {
				checked[idx] = true
			}
		}
	}

	m := checkboxModel{
		message:    cfg.Message,
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
		checked:    checked,
		pageSize:   cfg.PageSize,
		loop:       *cfg.Loop,
	}

	p := tea.NewProgram(m)
	finalModel, err := p.Run()
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrAborted, err)
	}

	final := finalModel.(checkboxModel)
	if final.aborted {
		return nil, ErrAborted
	}

	var result []any
	var names []string
	for _, idx := range selectable {
		if final.checked[idx] {
			result = append(result, choices[idx].value)
			names = append(names, choices[idx].name)
		}
	}

	display := "none"
	if len(names) > 0 {
		display = strings.Join(names, ", ")
	}
	fmt.Println(renderSuccess(cfg.Message, display))
	return result, nil
}
