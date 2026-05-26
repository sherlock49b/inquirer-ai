package prompt

import (
	"fmt"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

// searchDebounce is the delay before calling the source function after a
// keystroke.  This prevents hammering a slow source (HTTP, DB, etc.) on
// every character while the user is still typing.
const searchDebounce = 150 * time.Millisecond

// --- bubbletea messages ---

// searchResultMsg carries the choices returned by the source function.
type searchResultMsg struct {
	term    string
	choices []resolvedChoice
}

// searchTickMsg fires after the debounce period elapses.
type searchTickMsg struct {
	term string
}

// --- bubbletea model ---

type searchModel struct {
	message    string
	source     func(string) []ChoiceItem
	pageSize   int
	input      string
	choices    []resolvedChoice
	selectable []int
	cursor     int
	loading    bool
	done       bool
	aborted    bool
	// pendingTerm is the search term we are waiting to debounce.
	pendingTerm string
	// lastQueried is the term whose results are currently displayed.
	lastQueried string
}

func (m searchModel) Init() tea.Cmd {
	// Kick off the initial (empty-term) source fetch asynchronously.
	return fetchSource(m.source, "")
}

func (m searchModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {

	case searchResultMsg:
		// Only accept results that match the latest query we issued.
		if msg.term != m.lastQueried {
			return m, nil
		}
		m.choices = msg.choices
		m.selectable = selectableIndices(m.choices)
		m.loading = false
		if len(m.selectable) > 0 {
			m.cursor = m.selectable[0]
		} else {
			m.cursor = 0
		}
		return m, nil

	case searchTickMsg:
		// The debounce timer fired.  If the user kept typing the pending
		// term may have changed — only fetch if this tick is still current.
		if msg.term != m.input {
			return m, nil
		}
		m.lastQueried = msg.term
		m.loading = true
		return m, fetchSource(m.source, msg.term)

	case tea.KeyMsg:
		switch msg.String() {
		case "up", "ctrl+p":
			if len(m.selectable) > 0 {
				m.cursor = moveCursor(m.cursor, -1, m.selectable, true)
			}
		case "down", "ctrl+n":
			if len(m.selectable) > 0 {
				m.cursor = moveCursor(m.cursor, 1, m.selectable, true)
			}
		case "enter":
			m.done = true
			return m, tea.Quit
		case "ctrl+c":
			m.aborted = true
			return m, tea.Quit
		case "backspace":
			if len(m.input) > 0 {
				m.input = m.input[:len(m.input)-1]
				return m, m.debounceSearch()
			}
		default:
			// Ignore non-printable / multi-rune control sequences.
			if len(msg.String()) == 1 {
				ch := msg.String()[0]
				if ch >= 32 && ch < 127 {
					m.input += string(ch)
					return m, m.debounceSearch()
				}
			}
		}
	}
	return m, nil
}

// debounceSearch returns a tea.Cmd that waits for the debounce period and
// then sends a searchTickMsg with the current input.
func (m *searchModel) debounceSearch() tea.Cmd {
	term := m.input
	m.pendingTerm = term
	return tea.Tick(searchDebounce, func(_ time.Time) tea.Msg {
		return searchTickMsg{term: term}
	})
}

func (m searchModel) View() string {
	if m.done || m.aborted {
		return ""
	}

	var b strings.Builder
	b.WriteString(renderQuestion(m.message) + "\n")
	b.WriteString("  " + styleAnswer.Render(m.input) + styleMuted.Render("_") + "\n")

	if m.loading {
		b.WriteString(styleMuted.Render("  Searching...") + "\n")
		return b.String()
	}

	if len(m.selectable) == 0 {
		b.WriteString(styleMuted.Render("  No results") + "\n")
		return b.String()
	}

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
			b.WriteString(styleMuted.Render("  "+c.name+" (disabled)") + "\n")
			continue
		}
		if i == m.cursor {
			b.WriteString(stylePointer.Render(DefaultTheme.SymPointer) + " " + styleHighlight.Render(c.name) + "\n")
		} else {
			b.WriteString("  " + c.name + "\n")
		}
	}
	if end < len(m.choices) {
		b.WriteString(styleMuted.Render("  (more below)") + "\n")
	}

	return b.String()
}

// fetchSource returns a tea.Cmd that calls the source function in a
// goroutine — the standard bubbletea pattern for I/O.  The source
// function may perform blocking operations (HTTP requests, DB queries, file
// system walks, etc.) without freezing the terminal UI, because
// bubbletea runs every Cmd in its own goroutine.
func fetchSource(source func(string) []ChoiceItem, term string) tea.Cmd {
	return func() tea.Msg {
		items := source(term)
		return searchResultMsg{
			term:    term,
			choices: parseChoices(items),
		}
	}
}

func runSearchTUI(cfg SearchConfig) (any, error) {
	m := searchModel{
		message:  cfg.Message,
		source:   cfg.Source,
		pageSize: cfg.PageSize,
	}

	p := tea.NewProgram(m)
	finalModel, err := p.Run()
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrAborted, err)
	}

	final := finalModel.(searchModel)
	if final.aborted {
		return nil, ErrAborted
	}

	if len(final.selectable) == 0 || final.cursor >= len(final.choices) {
		return nil, fmt.Errorf("%w: no choice selected", ErrInvalidChoice)
	}

	c := final.choices[final.cursor]
	fmt.Println(renderSuccess(cfg.Message, c.name))
	return c.value, nil
}
