package prompt

import (
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// ── Fuzz: search source function with random terms ──

func FuzzSearchSource(f *testing.F) {
	f.Add("postgres")
	f.Add("")
	f.Add("   ")
	f.Add("a")
	f.Add("SELECT * FROM users;")
	f.Add("\x00\x01\x02")
	f.Add("emoji \U0001F525")
	f.Add(strings.Repeat("a", 10000))
	f.Add("line1\nline2\ttab")

	source := func(term string) []ChoiceItem {
		var items []ChoiceItem
		all := []Choice{
			{Name: "PostgreSQL", Value: "pg"},
			{Name: "MySQL", Value: "mysql"},
			{Name: "SQLite", Value: "sqlite"},
			{Name: "Redis", Value: "redis"},
		}
		lower := strings.ToLower(term)
		for _, c := range all {
			if term == "" || strings.Contains(strings.ToLower(c.Name), lower) {
				items = append(items, c)
			}
		}
		return items
	}

	f.Fuzz(func(t *testing.T, term string) {
		defer func() {
			if r := recover(); r != nil {
				t.Fatalf("source panicked on term %q: %v", term, r)
			}
		}()

		items := source(term)
		if items == nil {
			// nil is acceptable — it means no matches
			return
		}
		// Every returned item must be a valid ChoiceItem.
		for i, item := range items {
			if item == nil {
				t.Fatalf("source returned nil ChoiceItem at index %d for term %q", i, term)
			}
		}
		// parseChoices must not panic on the returned items.
		resolved := parseChoices(items)
		_ = selectableIndices(resolved)
	})
}

// ── Concurrent source calls: verify no data races ──

func TestSearchConcurrentSourceCalls(t *testing.T) {
	var callCount atomic.Int64

	source := func(term string) []ChoiceItem {
		callCount.Add(1)
		// Simulate a small amount of work
		time.Sleep(time.Millisecond)
		return []ChoiceItem{
			Choice{Name: "Result-" + term, Value: term},
		}
	}

	const goroutines = 50
	var wg sync.WaitGroup
	wg.Add(goroutines)

	// Shared slice to collect results — protected by mutex for the check,
	// but each goroutine writes to its own index to avoid false races.
	results := make([][]ChoiceItem, goroutines)

	for i := 0; i < goroutines; i++ {
		go func(idx int) {
			defer wg.Done()
			term := strings.Repeat("x", idx%10)
			items := source(term)
			results[idx] = items
		}(i)
	}

	wg.Wait()

	if callCount.Load() != goroutines {
		t.Fatalf("expected %d source calls, got %d", goroutines, callCount.Load())
	}

	for i, items := range results {
		if len(items) != 1 {
			t.Fatalf("goroutine %d: expected 1 item, got %d", i, len(items))
		}
	}
}

// ── Concurrent parseChoices: verify no races on shared data ──

func TestSearchConcurrentParseChoices(t *testing.T) {
	items := []ChoiceItem{
		Choice{Name: "Alpha", Value: "a"},
		Separator{Text: "---"},
		Choice{Name: "Beta", Value: "b"},
		Choice{Name: "Disabled", Value: "d", Disabled: true},
		Choice{Name: "Gamma", Value: "g"},
	}

	const goroutines = 100
	var wg sync.WaitGroup
	wg.Add(goroutines)

	for i := 0; i < goroutines; i++ {
		go func() {
			defer wg.Done()
			resolved := parseChoices(items)
			sel := selectableIndices(resolved)
			if len(sel) != 3 {
				t.Errorf("expected 3 selectable, got %d", len(sel))
			}
		}()
	}

	wg.Wait()
}

// ── Debounce correctness ──

func TestSearchDebounceCorrectness(t *testing.T) {
	source := func(term string) []ChoiceItem {
		return []ChoiceItem{Choice{Name: "R-" + term, Value: term}}
	}

	// Simulate the debounce behaviour from tui_search: only the term that
	// matches the current input when the tick fires should trigger a fetch.
	// We construct searchTickMsg values directly to avoid blocking on real
	// timers, testing the model's logic rather than tea.Tick timing.
	m := searchModel{
		message:  "test",
		source:   source,
		pageSize: 10,
		input:    "abc", // final user input after rapid typing
	}

	// Simulate three tick messages arriving: "a", "ab", "abc".
	// Only "abc" matches m.input, so the first two should be ignored.
	tick1 := searchTickMsg{term: "a"}
	tick2 := searchTickMsg{term: "ab"}
	tick3 := searchTickMsg{term: "abc"}

	// Stale tick "a" should be ignored (m.input is "abc").
	model1, c1 := m.Update(tick1)
	m = model1.(searchModel)
	if c1 != nil {
		t.Fatal("stale tick1 should produce no command")
	}

	// Stale tick "ab" should be ignored.
	model2, c2 := m.Update(tick2)
	m = model2.(searchModel)
	if c2 != nil {
		t.Fatal("stale tick2 should produce no command")
	}

	// Current tick "abc" matches m.input — should trigger fetch.
	model3, c3 := m.Update(tick3)
	m = model3.(searchModel)
	if c3 == nil {
		t.Fatal("tick3 should produce a fetchSource command")
	}
	if !m.loading {
		t.Fatal("model should be loading after valid tick")
	}
	if m.lastQueried != "abc" {
		t.Fatalf("lastQueried should be 'abc', got %q", m.lastQueried)
	}

	// Execute the fetch and deliver result.
	resultMsg := c3().(searchResultMsg)
	if resultMsg.term != "abc" {
		t.Fatalf("fetch should carry term 'abc', got %q", resultMsg.term)
	}
	model4, _ := m.Update(resultMsg)
	m = model4.(searchModel)
	if m.loading {
		t.Fatal("model should not be loading after result")
	}
	if len(m.choices) != 1 || m.choices[0].name != "R-abc" {
		t.Fatalf("expected choice 'R-abc', got %+v", m.choices)
	}
}

// ── Stale result rejection ──

func TestSearchStaleResultRejection(t *testing.T) {
	source := func(term string) []ChoiceItem {
		return []ChoiceItem{Choice{Name: "R-" + term, Value: term}}
	}

	m := searchModel{
		message:     "test",
		source:      source,
		pageSize:    10,
		lastQueried: "newer",
	}

	// Deliver a result for an older query.
	staleResult := searchResultMsg{
		term:    "older",
		choices: parseChoices([]ChoiceItem{Choice{Name: "stale", Value: "stale"}}),
	}
	model1, _ := m.Update(staleResult)
	m = model1.(searchModel)

	// Stale result should be discarded — choices remain nil/empty.
	if len(m.choices) != 0 {
		t.Fatalf("stale result should be discarded, but choices = %+v", m.choices)
	}

	// Now deliver a result for the current query.
	freshResult := searchResultMsg{
		term:    "newer",
		choices: parseChoices([]ChoiceItem{Choice{Name: "fresh", Value: "fresh"}}),
	}
	model2, _ := m.Update(freshResult)
	m = model2.(searchModel)

	if len(m.choices) != 1 || m.choices[0].name != "fresh" {
		t.Fatalf("fresh result should be accepted, got %+v", m.choices)
	}
}

// ── Stale result rejection with slow/fast source simulation ──

func TestSearchStaleResultSlowFastSource(t *testing.T) {
	// Simulate: query "slow" starts first but returns second;
	// query "fast" starts second but returns first.
	// Only "fast" results should be displayed.

	source := func(term string) []ChoiceItem {
		if term == "slow" {
			time.Sleep(50 * time.Millisecond)
		}
		return []ChoiceItem{Choice{Name: "R-" + term, Value: term}}
	}

	m := searchModel{
		message:  "test",
		source:   source,
		pageSize: 10,
	}

	// Simulate: user types "slow", tick fires, fetch starts.
	m.input = "slow"
	m.lastQueried = "slow"
	m.loading = true

	// User then types "fast" before "slow" returns.
	m.input = "fast"
	tickMsg := searchTickMsg{term: "fast"}
	model1, cmd := m.Update(tickMsg)
	m = model1.(searchModel)
	if cmd == nil {
		t.Fatal("should produce fetch command for 'fast'")
	}
	// lastQueried is now "fast"
	if m.lastQueried != "fast" {
		t.Fatalf("lastQueried should be 'fast', got %q", m.lastQueried)
	}

	// "slow" results arrive — should be rejected since lastQueried is "fast".
	slowResult := searchResultMsg{
		term:    "slow",
		choices: parseChoices(source("slow")),
	}
	model2, _ := m.Update(slowResult)
	m = model2.(searchModel)
	if len(m.choices) != 0 {
		t.Fatalf("slow (stale) result should be rejected, got %+v", m.choices)
	}

	// "fast" results arrive — should be accepted.
	fastResult := searchResultMsg{
		term:    "fast",
		choices: parseChoices(source("fast")),
	}
	model3, _ := m.Update(fastResult)
	m = model3.(searchModel)
	if len(m.choices) != 1 || m.choices[0].name != "R-fast" {
		t.Fatalf("expected 'R-fast', got %+v", m.choices)
	}
}

// ── Empty source results: no crash ──

func TestSearchEmptySourceResults(t *testing.T) {
	terms := []string{"", "anything", "  ", "\n", "\x00", strings.Repeat("z", 5000)}

	source := func(term string) []ChoiceItem {
		return []ChoiceItem{} // always empty
	}

	for _, term := range terms {
		t.Run("term="+truncate(term, 20), func(t *testing.T) {
			items := source(term)
			resolved := parseChoices(items)
			sel := selectableIndices(resolved)
			if len(sel) != 0 {
				t.Fatalf("expected 0 selectable for empty source, got %d", len(sel))
			}

			// Feed into model — verify no panic.
			m := searchModel{
				message:     "test",
				source:      source,
				pageSize:    10,
				lastQueried: term,
			}
			msg := searchResultMsg{term: term, choices: resolved}
			model, _ := m.Update(msg)
			final := model.(searchModel)
			if len(final.selectable) != 0 {
				t.Fatalf("expected 0 selectable in model, got %d", len(final.selectable))
			}
			// View should not panic.
			_ = final.View()
		})
	}
}

// ── Nil source return: no crash ──

func TestSearchNilSourceReturn(t *testing.T) {
	source := func(term string) []ChoiceItem {
		return nil
	}

	items := source("anything")
	resolved := parseChoices(items)
	sel := selectableIndices(resolved)
	if len(sel) != 0 {
		t.Fatalf("expected 0 selectable for nil source, got %d", len(sel))
	}

	m := searchModel{
		message:     "test",
		source:      source,
		pageSize:    10,
		lastQueried: "anything",
	}
	msg := searchResultMsg{term: "anything", choices: resolved}
	model, _ := m.Update(msg)
	final := model.(searchModel)
	_ = final.View()
}

// ── Source returns choices with empty names, very long names, control chars ──

func TestSearchSourceEdgeCaseNames(t *testing.T) {
	edgeCases := []ChoiceItem{
		Choice{Name: "", Value: "empty"},
		Choice{Name: strings.Repeat("A", 100000), Value: "long"},
		Choice{Name: "has\nnewline", Value: "newline"},
		Choice{Name: "has\ttab", Value: "tab"},
		Choice{Name: "has\x00null", Value: "null"},
		Choice{Name: "\x1b[31mred\x1b[0m", Value: "ansi"},
		Choice{Name: "normal", Value: "normal"},
		Separator{Text: ""},
		Separator{Text: "\n\n\n"},
	}

	source := func(term string) []ChoiceItem {
		return edgeCases
	}

	items := source("test")
	resolved := parseChoices(items)
	sel := selectableIndices(resolved)

	// 7 Choices (all enabled), 2 Separators => 7 selectable
	if len(sel) != 7 {
		t.Fatalf("expected 7 selectable, got %d", len(sel))
	}

	// Feed into model and render — verify no panic.
	m := searchModel{
		message:     "test",
		source:      source,
		pageSize:    5,
		lastQueried: "test",
		choices:     resolved,
		selectable:  sel,
		cursor:      sel[0],
	}
	view := m.View()
	if view == "" {
		t.Fatal("view should not be empty with choices present")
	}
}

// ── Concurrent fetchSource simulation: race detector validation ──

func TestSearchConcurrentFetchSource(t *testing.T) {
	source := func(term string) []ChoiceItem {
		// Simulate variable latency
		if len(term) > 3 {
			time.Sleep(2 * time.Millisecond)
		}
		return []ChoiceItem{
			Choice{Name: "R-" + term, Value: term},
		}
	}

	const goroutines = 50
	var wg sync.WaitGroup
	wg.Add(goroutines)

	for i := 0; i < goroutines; i++ {
		go func(idx int) {
			defer wg.Done()
			term := strings.Repeat("q", idx%8)
			cmd := fetchSource(source, term)
			msg := cmd()
			result, ok := msg.(searchResultMsg)
			if !ok {
				t.Errorf("expected searchResultMsg, got %T", msg)
				return
			}
			if result.term != term {
				t.Errorf("expected term %q, got %q", term, result.term)
			}
			if len(result.choices) != 1 {
				t.Errorf("expected 1 choice, got %d", len(result.choices))
			}
		}(i)
	}

	wg.Wait()
}

// ── Rapid sequential debounce simulation ──

func TestSearchRapidSequentialDebounce(t *testing.T) {
	source := func(term string) []ChoiceItem {
		return []ChoiceItem{Choice{Name: "R-" + term, Value: term}}
	}

	m := searchModel{
		message:  "test",
		source:   source,
		pageSize: 10,
		input:    "hello", // final state after rapid typing
	}

	// Simulate tick messages arriving for each intermediate keystroke.
	// The model should ignore all ticks that do not match m.input.
	staleTerms := []string{"h", "he", "hel", "hell"}
	for _, term := range staleTerms {
		tick := searchTickMsg{term: term}
		model, cmd := m.Update(tick)
		m = model.(searchModel)
		if cmd != nil {
			t.Fatalf("stale tick %q should not produce a command", term)
		}
	}

	// The tick for "hello" matches m.input — should trigger fetch.
	finalTick := searchTickMsg{term: "hello"}
	model, cmd := m.Update(finalTick)
	m = model.(searchModel)
	if cmd == nil {
		t.Fatal("final tick should produce fetch command")
	}

	// Execute the fetch.
	fetchResult := cmd().(searchResultMsg)
	model2, _ := m.Update(fetchResult)
	m = model2.(searchModel)

	if len(m.choices) != 1 || m.choices[0].name != "R-hello" {
		t.Fatalf("expected 'R-hello', got %+v", m.choices)
	}
}

// ── Helper ──

// truncate shortens s for use in subtest names.
func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max] + "..."
}
