package prompt

import (
	"regexp"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
)

// stripAnsi removes ANSI escape sequences from a string so we can assert on
// plain-text content rendered by lipgloss styles.
func stripAnsi(s string) string {
	re := regexp.MustCompile(`\x1b\[[0-9;]*m`)
	return re.ReplaceAllString(s, "")
}

// --- helper builders ---

func makeSelectModel(names []string, loop bool) selectModel {
	var choices []resolvedChoice
	for _, n := range names {
		choices = append(choices, resolvedChoice{name: n, value: n, selectable: true})
	}
	selectable := selectableIndices(choices)
	return selectModel{
		message:    "Pick one",
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
		pageSize:   10,
		loop:       loop,
	}
}

func makeCheckboxModel(names []string, loop bool) checkboxModel {
	var choices []resolvedChoice
	for _, n := range names {
		choices = append(choices, resolvedChoice{name: n, value: n, selectable: true})
	}
	selectable := selectableIndices(choices)
	return checkboxModel{
		message:    "Select items",
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
		checked:    make(map[int]bool),
		pageSize:   10,
		loop:       loop,
	}
}

func makeSearchModel(items []string) searchModel {
	var choices []resolvedChoice
	for _, n := range items {
		choices = append(choices, resolvedChoice{name: n, value: n, selectable: true})
	}
	selectable := selectableIndices(choices)
	cursor := 0
	if len(selectable) > 0 {
		cursor = selectable[0]
	}
	return searchModel{
		message:    "Search",
		source:     func(term string) []ChoiceItem { return nil }, // not used in direct model tests
		pageSize:   10,
		choices:    choices,
		selectable: selectable,
		cursor:     cursor,
	}
}

func keyMsg(key string) tea.KeyMsg {
	// Map well-known key names to tea.KeyType, otherwise use tea.KeyRunes.
	switch key {
	case "enter":
		return tea.KeyMsg{Type: tea.KeyEnter}
	case "up":
		return tea.KeyMsg{Type: tea.KeyUp}
	case "down":
		return tea.KeyMsg{Type: tea.KeyDown}
	case "backspace":
		return tea.KeyMsg{Type: tea.KeyBackspace}
	case "ctrl+c":
		return tea.KeyMsg{Type: tea.KeyCtrlC}
	case "ctrl+p":
		return tea.KeyMsg{Type: tea.KeyCtrlP}
	case "ctrl+n":
		return tea.KeyMsg{Type: tea.KeyCtrlN}
	default:
		return tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(key)}
	}
}

// ============================================================
// selectModel tests
// ============================================================

func TestTuiModelSelectInitialView(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta", "Gamma"}, true)
	view := stripAnsi(m.View())

	if !strings.Contains(view, "Pick one") {
		t.Fatalf("expected message in view, got:\n%s", view)
	}
	for _, name := range []string{"Alpha", "Beta", "Gamma"} {
		if !strings.Contains(view, name) {
			t.Fatalf("expected choice %q in view, got:\n%s", name, view)
		}
	}
	// First choice should have the pointer symbol
	if !strings.Contains(view, DefaultTheme.SymPointer) {
		t.Fatalf("expected pointer symbol in view, got:\n%s", view)
	}
}

func TestTuiModelSelectCursorDown(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta", "Gamma"}, true)

	updated, _ := m.Update(keyMsg("down"))
	m2 := updated.(selectModel)

	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 after down, got %d", m2.cursor)
	}

	view := stripAnsi(m2.View())
	// "Beta" should now be the highlighted line (preceded by pointer)
	lines := strings.Split(view, "\n")
	foundPointerBeta := false
	for _, line := range lines {
		if strings.Contains(line, DefaultTheme.SymPointer) && strings.Contains(line, "Beta") {
			foundPointerBeta = true
			break
		}
	}
	if !foundPointerBeta {
		t.Fatalf("expected pointer on Beta after down, got:\n%s", view)
	}
}

func TestTuiModelSelectCursorUp(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta", "Gamma"}, true)

	// With loop=true, pressing up from first item should wrap to last
	updated, _ := m.Update(keyMsg("up"))
	m2 := updated.(selectModel)

	if m2.cursor != 2 {
		t.Fatalf("expected cursor at 2 (wrapped) after up, got %d", m2.cursor)
	}
}

func TestTuiModelSelectCursorUpNoLoop(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta", "Gamma"}, false)

	// With loop=false, pressing up from first item should stay at first
	updated, _ := m.Update(keyMsg("up"))
	m2 := updated.(selectModel)

	if m2.cursor != 0 {
		t.Fatalf("expected cursor to stay at 0 (no loop), got %d", m2.cursor)
	}
}

func TestTuiModelSelectEnterSelection(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta", "Gamma"}, true)

	// Move down twice to "Gamma"
	updated, _ := m.Update(keyMsg("down"))
	updated, _ = updated.(selectModel).Update(keyMsg("down"))
	m2 := updated.(selectModel)

	if m2.cursor != 2 {
		t.Fatalf("expected cursor at 2, got %d", m2.cursor)
	}

	// Press enter to select
	updated, cmd := m2.Update(keyMsg("enter"))
	m3 := updated.(selectModel)

	if !m3.done {
		t.Fatal("expected done=true after enter")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command after enter")
	}
	// View should be empty when done
	if m3.View() != "" {
		t.Fatalf("expected empty view when done, got %q", m3.View())
	}
}

func TestTuiModelSelectDigitJump(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta", "Gamma", "Delta"}, true)

	// Press '2' to jump to the 2nd selectable choice (Beta)
	updated, _ := m.Update(keyMsg("2"))
	m2 := updated.(selectModel)

	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 after pressing '2', got %d", m2.cursor)
	}

	// Press '4' to jump to the 4th selectable choice (Delta)
	updated, _ = m2.Update(keyMsg("4"))
	m3 := updated.(selectModel)

	if m3.cursor != 3 {
		t.Fatalf("expected cursor at 3 after pressing '4', got %d", m3.cursor)
	}
}

func TestTuiModelSelectDigitJumpClamps(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta"}, true)

	// Press '9' — should clamp to last selectable (index 1)
	updated, _ := m.Update(keyMsg("9"))
	m2 := updated.(selectModel)

	if m2.cursor != 1 {
		t.Fatalf("expected cursor clamped to 1, got %d", m2.cursor)
	}
}

func TestTuiModelSelectWithDisabledChoices(t *testing.T) {
	choices := []resolvedChoice{
		{name: "Alpha", value: "a", selectable: true},
		{name: "Beta (disabled)", value: "b", selectable: false},
		{name: "Gamma", value: "c", selectable: true},
	}
	selectable := selectableIndices(choices)
	m := selectModel{
		message:    "Pick one",
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
		pageSize:   10,
		loop:       true,
	}

	view := stripAnsi(m.View())
	if !strings.Contains(view, "(disabled)") {
		t.Fatalf("expected '(disabled)' in view for disabled choice, got:\n%s", view)
	}

	// Pressing down should skip disabled and go to Gamma (index 2)
	updated, _ := m.Update(keyMsg("down"))
	m2 := updated.(selectModel)

	if m2.cursor != 2 {
		t.Fatalf("expected cursor to skip disabled choice, got cursor=%d", m2.cursor)
	}
}

func TestTuiModelSelectWithSeparator(t *testing.T) {
	choices := []resolvedChoice{
		{name: "Alpha", value: "a", selectable: true},
		{name: "────────", isSeparator: true},
		{name: "Beta", value: "b", selectable: true},
	}
	selectable := selectableIndices(choices)
	m := selectModel{
		message:    "Pick one",
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
		pageSize:   10,
		loop:       true,
	}

	view := stripAnsi(m.View())
	if !strings.Contains(view, "────────") {
		t.Fatalf("expected separator in view, got:\n%s", view)
	}

	// Down should skip separator and land on Beta (index 2)
	updated, _ := m.Update(keyMsg("down"))
	m2 := updated.(selectModel)

	if m2.cursor != 2 {
		t.Fatalf("expected cursor to skip separator, got cursor=%d", m2.cursor)
	}
}

func TestTuiModelSelectAbort(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta"}, true)

	updated, cmd := m.Update(keyMsg("ctrl+c"))
	m2 := updated.(selectModel)

	if !m2.aborted {
		t.Fatal("expected aborted=true after ctrl+c")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command after ctrl+c")
	}
	if m2.View() != "" {
		t.Fatalf("expected empty view when aborted, got %q", m2.View())
	}
}

// 'q' must NOT abort (Ctrl-C only), per the spec-strict parity decision.
func TestTuiModelSelectQDoesNotAbort(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta"}, true)

	updated, cmd := m.Update(keyMsg("q"))
	m2 := updated.(selectModel)

	if m2.aborted {
		t.Fatal("'q' must not abort the select prompt")
	}
	if cmd != nil {
		t.Fatal("'q' must not emit a quit command")
	}

	// Ctrl-C still aborts.
	updated, cmd = m.Update(keyMsg("ctrl+c"))
	m3 := updated.(selectModel)
	if !m3.aborted {
		t.Fatal("expected aborted=true after ctrl+c")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command after ctrl+c")
	}
}

func TestTuiModelSelectVimKeys(t *testing.T) {
	m := makeSelectModel([]string{"Alpha", "Beta", "Gamma"}, true)

	// 'j' moves down
	updated, _ := m.Update(keyMsg("j"))
	m2 := updated.(selectModel)
	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 after 'j', got %d", m2.cursor)
	}

	// 'k' moves up
	updated, _ = m2.Update(keyMsg("k"))
	m3 := updated.(selectModel)
	if m3.cursor != 0 {
		t.Fatalf("expected cursor at 0 after 'k', got %d", m3.cursor)
	}
}

func TestTuiModelSelectEmptyChoices(t *testing.T) {
	// Constructing a model with no selectable choices should be guarded by
	// the outer Select() function, but the View should still not panic.
	m := selectModel{
		message:    "Pick one",
		choices:    nil,
		selectable: nil,
		cursor:     0,
		pageSize:   10,
		loop:       true,
	}

	// View should not panic
	view := m.View()
	if !strings.Contains(stripAnsi(view), "Pick one") {
		t.Fatalf("expected message in empty view, got:\n%s", view)
	}
}

func TestTuiModelSelectPagination(t *testing.T) {
	// Create 20 choices with pageSize 5 to test pagination indicators
	names := make([]string, 20)
	for i := range names {
		names[i] = strings.Repeat("Item", 1) + string(rune('A'+i))
	}
	choices := make([]resolvedChoice, 20)
	for i, n := range names {
		choices[i] = resolvedChoice{name: n, value: n, selectable: true}
	}
	selectable := selectableIndices(choices)

	m := selectModel{
		message:    "Pick one",
		choices:    choices,
		selectable: selectable,
		cursor:     10, // middle
		pageSize:   5,
		loop:       true,
	}

	view := stripAnsi(m.View())
	if !strings.Contains(view, "(more above)") {
		t.Fatalf("expected '(more above)' in paginated view, got:\n%s", view)
	}
	if !strings.Contains(view, "(more below)") {
		t.Fatalf("expected '(more below)' in paginated view, got:\n%s", view)
	}
}

// ============================================================
// checkboxModel tests
// ============================================================

func TestTuiModelCheckboxInitialView(t *testing.T) {
	m := makeCheckboxModel([]string{"Docker", "CI", "Tests"}, true)
	view := stripAnsi(m.View())

	if !strings.Contains(view, "Select items") {
		t.Fatalf("expected message in view, got:\n%s", view)
	}
	for _, name := range []string{"Docker", "CI", "Tests"} {
		if !strings.Contains(view, name) {
			t.Fatalf("expected choice %q in view, got:\n%s", name, view)
		}
	}
	// All choices should be unchecked initially
	uncheckedCount := strings.Count(view, DefaultTheme.SymUnchecked)
	if uncheckedCount < 3 {
		t.Fatalf("expected at least 3 unchecked symbols, got %d in:\n%s", uncheckedCount, view)
	}
	// No checked symbols should appear
	if strings.Contains(view, DefaultTheme.SymChecked) {
		t.Fatalf("expected no checked symbols initially, got:\n%s", view)
	}
}

func TestTuiModelCheckboxSpaceToggles(t *testing.T) {
	m := makeCheckboxModel([]string{"Docker", "CI", "Tests"}, true)

	// Space toggles the current item
	updated, _ := m.Update(keyMsg(" "))
	m2 := updated.(checkboxModel)

	if !m2.checked[0] {
		t.Fatal("expected first item to be checked after space")
	}

	view := stripAnsi(m2.View())
	if !strings.Contains(view, DefaultTheme.SymChecked) {
		t.Fatalf("expected checked symbol in view after toggling, got:\n%s", view)
	}

	// Space again toggles it off
	updated, _ = m2.Update(keyMsg(" "))
	m3 := updated.(checkboxModel)

	if m3.checked[0] {
		t.Fatal("expected first item to be unchecked after second space")
	}
}

func TestTuiModelCheckboxCursorNavigation(t *testing.T) {
	m := makeCheckboxModel([]string{"Docker", "CI", "Tests"}, true)

	// Move down
	updated, _ := m.Update(keyMsg("down"))
	m2 := updated.(checkboxModel)
	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 after down, got %d", m2.cursor)
	}

	// Move down again
	updated, _ = m2.Update(keyMsg("down"))
	m3 := updated.(checkboxModel)
	if m3.cursor != 2 {
		t.Fatalf("expected cursor at 2 after second down, got %d", m3.cursor)
	}

	// Loop back to first
	updated, _ = m3.Update(keyMsg("down"))
	m4 := updated.(checkboxModel)
	if m4.cursor != 0 {
		t.Fatalf("expected cursor to loop to 0, got %d", m4.cursor)
	}
}

func TestTuiModelCheckboxEnterSubmits(t *testing.T) {
	m := makeCheckboxModel([]string{"Docker", "CI", "Tests"}, true)

	// Check first and third items
	updated, _ := m.Update(keyMsg(" "))                         // check Docker
	updated, _ = updated.(checkboxModel).Update(keyMsg("down")) // move to CI
	updated, _ = updated.(checkboxModel).Update(keyMsg("down")) // move to Tests
	updated, _ = updated.(checkboxModel).Update(keyMsg(" "))    // check Tests

	// Submit
	updated, cmd := updated.(checkboxModel).Update(keyMsg("enter"))
	m2 := updated.(checkboxModel)

	if !m2.done {
		t.Fatal("expected done=true after enter")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command after enter")
	}
	if !m2.checked[0] {
		t.Fatal("expected Docker (index 0) to remain checked")
	}
	if m2.checked[1] {
		t.Fatal("expected CI (index 1) to remain unchecked")
	}
	if !m2.checked[2] {
		t.Fatal("expected Tests (index 2) to remain checked")
	}
}

func TestTuiModelCheckboxSelectAll(t *testing.T) {
	m := makeCheckboxModel([]string{"Docker", "CI", "Tests"}, true)

	// Press 'a' to select all
	updated, _ := m.Update(keyMsg("a"))
	m2 := updated.(checkboxModel)

	for _, idx := range m2.selectable {
		if !m2.checked[idx] {
			t.Fatalf("expected index %d to be checked after select-all", idx)
		}
	}

	view := stripAnsi(m2.View())
	checkedCount := strings.Count(view, DefaultTheme.SymChecked)
	if checkedCount != 3 {
		t.Fatalf("expected 3 checked symbols after select-all, got %d in:\n%s", checkedCount, view)
	}

	// Press 'a' again to deselect all
	updated, _ = m2.Update(keyMsg("a"))
	m3 := updated.(checkboxModel)

	for _, idx := range m3.selectable {
		if m3.checked[idx] {
			t.Fatalf("expected index %d to be unchecked after deselect-all", idx)
		}
	}
}

func TestTuiModelCheckboxWithDisabled(t *testing.T) {
	choices := []resolvedChoice{
		{name: "Alpha", value: "a", selectable: true},
		{name: "Beta", value: "b", selectable: false},
		{name: "Gamma", value: "c", selectable: true},
	}
	selectable := selectableIndices(choices)
	m := checkboxModel{
		message:    "Select items",
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
		checked:    make(map[int]bool),
		pageSize:   10,
		loop:       true,
	}

	view := stripAnsi(m.View())
	if !strings.Contains(view, "(disabled)") {
		t.Fatalf("expected '(disabled)' in view, got:\n%s", view)
	}

	// Down should skip disabled
	updated, _ := m.Update(keyMsg("down"))
	m2 := updated.(checkboxModel)
	if m2.cursor != 2 {
		t.Fatalf("expected cursor to skip disabled, got cursor=%d", m2.cursor)
	}
}

func TestTuiModelCheckboxAbort(t *testing.T) {
	m := makeCheckboxModel([]string{"Alpha", "Beta"}, true)

	updated, cmd := m.Update(keyMsg("ctrl+c"))
	m2 := updated.(checkboxModel)

	if !m2.aborted {
		t.Fatal("expected aborted=true after ctrl+c")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command")
	}
	if m2.View() != "" {
		t.Fatalf("expected empty view when aborted, got %q", m2.View())
	}
}

// 'q' must NOT abort (Ctrl-C only), per the spec-strict parity decision.
func TestTuiModelCheckboxQDoesNotAbort(t *testing.T) {
	m := makeCheckboxModel([]string{"Alpha", "Beta"}, true)

	updated, cmd := m.Update(keyMsg("q"))
	m2 := updated.(checkboxModel)

	if m2.aborted {
		t.Fatal("'q' must not abort the checkbox prompt")
	}
	if cmd != nil {
		t.Fatal("'q' must not emit a quit command")
	}

	// Ctrl-C still aborts.
	updated, cmd = m.Update(keyMsg("ctrl+c"))
	m3 := updated.(checkboxModel)
	if !m3.aborted {
		t.Fatal("expected aborted=true after ctrl+c")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command after ctrl+c")
	}
}

func TestTuiModelCheckboxVimKeys(t *testing.T) {
	m := makeCheckboxModel([]string{"Alpha", "Beta", "Gamma"}, true)

	updated, _ := m.Update(keyMsg("j"))
	m2 := updated.(checkboxModel)
	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 after 'j', got %d", m2.cursor)
	}

	updated, _ = m2.Update(keyMsg("k"))
	m3 := updated.(checkboxModel)
	if m3.cursor != 0 {
		t.Fatalf("expected cursor at 0 after 'k', got %d", m3.cursor)
	}
}

func TestTuiModelCheckboxWithSeparator(t *testing.T) {
	choices := []resolvedChoice{
		{name: "Alpha", value: "a", selectable: true},
		{name: "---divider---", isSeparator: true},
		{name: "Beta", value: "b", selectable: true},
	}
	selectable := selectableIndices(choices)
	m := checkboxModel{
		message:    "Select",
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
		checked:    make(map[int]bool),
		pageSize:   10,
		loop:       true,
	}

	view := stripAnsi(m.View())
	if !strings.Contains(view, "---divider---") {
		t.Fatalf("expected separator text in view, got:\n%s", view)
	}
}

func TestTuiModelCheckboxPagination(t *testing.T) {
	choices := make([]resolvedChoice, 20)
	for i := range choices {
		choices[i] = resolvedChoice{name: strings.Repeat("C", 1) + string(rune('A'+i)), value: i, selectable: true}
	}
	selectable := selectableIndices(choices)

	m := checkboxModel{
		message:    "Select",
		choices:    choices,
		selectable: selectable,
		cursor:     10,
		checked:    make(map[int]bool),
		pageSize:   5,
		loop:       true,
	}

	view := stripAnsi(m.View())
	if !strings.Contains(view, "(more above)") {
		t.Fatalf("expected '(more above)', got:\n%s", view)
	}
	if !strings.Contains(view, "(more below)") {
		t.Fatalf("expected '(more below)', got:\n%s", view)
	}
}

// ============================================================
// searchModel tests
// ============================================================

func TestTuiModelSearchInitialView(t *testing.T) {
	m := makeSearchModel([]string{"Apple", "Banana", "Cherry"})
	view := stripAnsi(m.View())

	if !strings.Contains(view, "Search") {
		t.Fatalf("expected message in view, got:\n%s", view)
	}
	// Should show the input area (underscore cursor)
	if !strings.Contains(view, "_") {
		t.Fatalf("expected input cursor '_' in view, got:\n%s", view)
	}
	// Choices should be visible
	for _, name := range []string{"Apple", "Banana", "Cherry"} {
		if !strings.Contains(view, name) {
			t.Fatalf("expected choice %q in view, got:\n%s", name, view)
		}
	}
}

func TestTuiModelSearchCharacterInput(t *testing.T) {
	m := makeSearchModel([]string{"Apple", "Banana", "Cherry"})

	// Type 'a'
	updated, _ := m.Update(keyMsg("a"))
	m2 := updated.(searchModel)

	if m2.input != "a" {
		t.Fatalf("expected input 'a', got %q", m2.input)
	}

	// Type 'p'
	updated, _ = m2.Update(keyMsg("p"))
	m3 := updated.(searchModel)

	if m3.input != "ap" {
		t.Fatalf("expected input 'ap', got %q", m3.input)
	}

	view := stripAnsi(m3.View())
	if !strings.Contains(view, "ap") {
		t.Fatalf("expected 'ap' in search input display, got:\n%s", view)
	}
}

func TestTuiModelSearchBackspace(t *testing.T) {
	m := makeSearchModel([]string{"Apple", "Banana"})

	// Type "abc"
	updated, _ := m.Update(keyMsg("a"))
	updated, _ = updated.(searchModel).Update(keyMsg("b"))
	updated, _ = updated.(searchModel).Update(keyMsg("c"))
	m2 := updated.(searchModel)
	if m2.input != "abc" {
		t.Fatalf("expected input 'abc', got %q", m2.input)
	}

	// Backspace
	updated, _ = m2.Update(keyMsg("backspace"))
	m3 := updated.(searchModel)
	if m3.input != "ab" {
		t.Fatalf("expected input 'ab' after backspace, got %q", m3.input)
	}
}

func TestTuiModelSearchBackspaceOnEmpty(t *testing.T) {
	m := makeSearchModel([]string{"Apple"})

	// Backspace on empty input should be a no-op
	updated, _ := m.Update(keyMsg("backspace"))
	m2 := updated.(searchModel)

	if m2.input != "" {
		t.Fatalf("expected empty input after backspace on empty, got %q", m2.input)
	}
}

func TestTuiModelSearchCursorNavigation(t *testing.T) {
	m := makeSearchModel([]string{"Apple", "Banana", "Cherry"})

	// Down
	updated, _ := m.Update(keyMsg("down"))
	m2 := updated.(searchModel)
	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 after down, got %d", m2.cursor)
	}

	// Down again
	updated, _ = m2.Update(keyMsg("down"))
	m3 := updated.(searchModel)
	if m3.cursor != 2 {
		t.Fatalf("expected cursor at 2 after second down, got %d", m3.cursor)
	}

	// Up
	updated, _ = m3.Update(keyMsg("up"))
	m4 := updated.(searchModel)
	if m4.cursor != 1 {
		t.Fatalf("expected cursor at 1 after up, got %d", m4.cursor)
	}
}

func TestTuiModelSearchCtrlPCtrlN(t *testing.T) {
	m := makeSearchModel([]string{"Apple", "Banana", "Cherry"})

	// ctrl+n moves down
	updated, _ := m.Update(keyMsg("ctrl+n"))
	m2 := updated.(searchModel)
	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 after ctrl+n, got %d", m2.cursor)
	}

	// ctrl+p moves up
	updated, _ = m2.Update(keyMsg("ctrl+p"))
	m3 := updated.(searchModel)
	if m3.cursor != 0 {
		t.Fatalf("expected cursor at 0 after ctrl+p, got %d", m3.cursor)
	}
}

func TestTuiModelSearchEnterSelects(t *testing.T) {
	m := makeSearchModel([]string{"Apple", "Banana", "Cherry"})

	// Move to Banana and select
	updated, _ := m.Update(keyMsg("down"))
	updated, cmd := updated.(searchModel).Update(keyMsg("enter"))
	m2 := updated.(searchModel)

	if !m2.done {
		t.Fatal("expected done=true after enter")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command after enter")
	}
	if m2.cursor != 1 {
		t.Fatalf("expected cursor at 1 (Banana), got %d", m2.cursor)
	}
}

func TestTuiModelSearchAbort(t *testing.T) {
	m := makeSearchModel([]string{"Apple"})

	updated, cmd := m.Update(keyMsg("ctrl+c"))
	m2 := updated.(searchModel)

	if !m2.aborted {
		t.Fatal("expected aborted=true after ctrl+c")
	}
	if cmd == nil {
		t.Fatal("expected tea.Quit command")
	}
	if m2.View() != "" {
		t.Fatalf("expected empty view when aborted, got %q", m2.View())
	}
}

func TestTuiModelSearchLoadingView(t *testing.T) {
	m := makeSearchModel(nil) // no choices yet
	m.loading = true

	view := stripAnsi(m.View())
	if !strings.Contains(view, "Searching...") {
		t.Fatalf("expected 'Searching...' in loading view, got:\n%s", view)
	}
}

func TestTuiModelSearchNoResults(t *testing.T) {
	m := makeSearchModel(nil) // no choices, not loading
	m.loading = false

	view := stripAnsi(m.View())
	if !strings.Contains(view, "No results") {
		t.Fatalf("expected 'No results' in view, got:\n%s", view)
	}
}

func TestTuiModelSearchResultMsg(t *testing.T) {
	m := searchModel{
		message:     "Search",
		source:      func(term string) []ChoiceItem { return nil },
		pageSize:    10,
		loading:     true,
		lastQueried: "test",
	}

	// Simulate receiving search results
	results := searchResultMsg{
		term: "test",
		choices: []resolvedChoice{
			{name: "Result1", value: "r1", selectable: true},
			{name: "Result2", value: "r2", selectable: true},
		},
	}

	updated, _ := m.Update(results)
	m2 := updated.(searchModel)

	if m2.loading {
		t.Fatal("expected loading=false after receiving results")
	}
	if len(m2.choices) != 2 {
		t.Fatalf("expected 2 choices, got %d", len(m2.choices))
	}
	if m2.cursor != 0 {
		t.Fatalf("expected cursor at 0, got %d", m2.cursor)
	}

	view := stripAnsi(m2.View())
	if !strings.Contains(view, "Result1") || !strings.Contains(view, "Result2") {
		t.Fatalf("expected results in view, got:\n%s", view)
	}
}

func TestTuiModelSearchResultMsgStaleIgnored(t *testing.T) {
	m := searchModel{
		message:     "Search",
		source:      func(term string) []ChoiceItem { return nil },
		pageSize:    10,
		loading:     true,
		lastQueried: "current",
	}

	// Simulate stale results (term doesn't match lastQueried)
	stale := searchResultMsg{
		term: "old",
		choices: []resolvedChoice{
			{name: "Stale", value: "s", selectable: true},
		},
	}

	updated, _ := m.Update(stale)
	m2 := updated.(searchModel)

	// Should still be loading, choices unchanged
	if !m2.loading {
		t.Fatal("expected loading to remain true for stale results")
	}
	if len(m2.choices) != 0 {
		t.Fatalf("expected no choices (stale results ignored), got %d", len(m2.choices))
	}
}

func TestTuiModelSearchTickMsg(t *testing.T) {
	var fetchedTerm string
	m := searchModel{
		message:  "Search",
		source:   func(term string) []ChoiceItem { fetchedTerm = term; return nil },
		pageSize: 10,
		input:    "hello",
	}

	// Simulate the debounce tick firing with matching term
	tick := searchTickMsg{term: "hello"}
	updated, cmd := m.Update(tick)
	m2 := updated.(searchModel)

	if !m2.loading {
		t.Fatal("expected loading=true after tick")
	}
	if m2.lastQueried != "hello" {
		t.Fatalf("expected lastQueried='hello', got %q", m2.lastQueried)
	}
	if cmd == nil {
		t.Fatal("expected fetchSource command from tick")
	}

	// Execute the command to verify the source is called
	msg := cmd()
	result, ok := msg.(searchResultMsg)
	if !ok {
		t.Fatalf("expected searchResultMsg, got %T", msg)
	}
	if result.term != "hello" {
		t.Fatalf("expected term 'hello', got %q", result.term)
	}
	if fetchedTerm != "hello" {
		t.Fatalf("expected source called with 'hello', got %q", fetchedTerm)
	}
}

func TestTuiModelSearchTickMsgStaleIgnored(t *testing.T) {
	m := searchModel{
		message:  "Search",
		source:   func(term string) []ChoiceItem { return nil },
		pageSize: 10,
		input:    "current",
	}

	// Tick with old term should be ignored
	tick := searchTickMsg{term: "old"}
	updated, cmd := m.Update(tick)
	m2 := updated.(searchModel)

	if m2.loading {
		t.Fatal("expected loading=false for stale tick")
	}
	if cmd != nil {
		t.Fatal("expected no command for stale tick")
	}
}

func TestTuiModelSearchWithDisabledChoices(t *testing.T) {
	choices := []resolvedChoice{
		{name: "Alpha", value: "a", selectable: true},
		{name: "Beta", value: "b", selectable: false},
		{name: "Gamma", value: "c", selectable: true},
	}
	selectable := selectableIndices(choices)
	m := searchModel{
		message:    "Search",
		source:     func(term string) []ChoiceItem { return nil },
		pageSize:   10,
		choices:    choices,
		selectable: selectable,
		cursor:     selectable[0],
	}

	view := stripAnsi(m.View())
	if !strings.Contains(view, "(disabled)") {
		t.Fatalf("expected '(disabled)' in view, got:\n%s", view)
	}
}

func TestTuiModelSearchNavigationWraps(t *testing.T) {
	m := makeSearchModel([]string{"Apple", "Banana", "Cherry"})

	// Search model uses loop=true internally for moveCursor
	// Move up from first item should wrap to last
	updated, _ := m.Update(keyMsg("up"))
	m2 := updated.(searchModel)
	if m2.cursor != 2 {
		t.Fatalf("expected cursor to wrap to 2, got %d", m2.cursor)
	}

	// Move down from last should wrap to first
	updated, _ = m2.Update(keyMsg("down"))
	m3 := updated.(searchModel)
	if m3.cursor != 0 {
		t.Fatalf("expected cursor to wrap to 0, got %d", m3.cursor)
	}
}

func TestTuiModelSearchIgnoresControlSequences(t *testing.T) {
	m := makeSearchModel([]string{"Apple"})

	// Multi-byte control sequences should be ignored (not added to input)
	// Simulate a key that has len > 1 but isn't a recognized key
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("ab")})
	m2 := updated.(searchModel)

	// The model checks len(msg.String()) == 1, so "ab" should be ignored
	if m2.input != "" {
		t.Fatalf("expected input to remain empty for multi-rune key, got %q", m2.input)
	}
}

func TestTuiModelSearchPagination(t *testing.T) {
	items := make([]string, 20)
	for i := range items {
		items[i] = "Item" + string(rune('A'+i))
	}
	m := makeSearchModel(items)
	m.pageSize = 5
	m.cursor = 10

	view := stripAnsi(m.View())
	if !strings.Contains(view, "(more above)") {
		t.Fatalf("expected '(more above)', got:\n%s", view)
	}
	if !strings.Contains(view, "(more below)") {
		t.Fatalf("expected '(more below)', got:\n%s", view)
	}
}

// ============================================================
// stripAnsi helper test
// ============================================================

func TestStripAnsi(t *testing.T) {
	input := "\x1b[1;31mHello\x1b[0m \x1b[32mWorld\x1b[0m"
	want := "Hello World"
	got := stripAnsi(input)
	if got != want {
		t.Fatalf("stripAnsi(%q) = %q, want %q", input, got, want)
	}
}

func TestStripAnsiPlainText(t *testing.T) {
	input := "no codes here"
	got := stripAnsi(input)
	if got != input {
		t.Fatalf("stripAnsi(%q) = %q, want %q", input, got, input)
	}
}

func TestStripAnsiEmpty(t *testing.T) {
	got := stripAnsi("")
	if got != "" {
		t.Fatalf("stripAnsi('') = %q, want ''", got)
	}
}

// ============================================================
// Init() returns nil for all models
// ============================================================

func TestTuiModelSelectInit(t *testing.T) {
	m := makeSelectModel([]string{"A"}, true)
	cmd := m.Init()
	if cmd != nil {
		t.Fatal("selectModel.Init() should return nil")
	}
}

func TestTuiModelCheckboxInit(t *testing.T) {
	m := makeCheckboxModel([]string{"A"}, true)
	cmd := m.Init()
	if cmd != nil {
		t.Fatal("checkboxModel.Init() should return nil")
	}
}

func TestTuiModelSearchInit(t *testing.T) {
	// searchModel.Init() returns a fetchSource command, not nil
	m := searchModel{
		message: "Search",
		source:  func(term string) []ChoiceItem { return nil },
	}
	cmd := m.Init()
	if cmd == nil {
		t.Fatal("searchModel.Init() should return a command (fetchSource)")
	}
}
