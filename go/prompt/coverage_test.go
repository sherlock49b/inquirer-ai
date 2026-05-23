package prompt

import (
	"errors"
	"fmt"
	"testing"
)

// ── Confirm: filter, validate, string coercion coverage ──

func TestConfirmFilterApplied(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":true}`+"\n")
	defer cleanup()

	inverted := false
	result, err := Confirm(ConfirmConfig{
		Message: "Q",
		Filter: func(v any) any {
			if b, ok := v.(bool); ok {
				inverted = true
				return !b
			}
			return v
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !inverted {
		t.Fatal("filter was not called")
	}
	if result != false {
		t.Fatal("filter should have inverted true to false")
	}
}

func TestConfirmValidateRejects(t *testing.T) {
	// Provide 3 answers for retry loop.
	input := `{"answer":false}` + "\n" +
		`{"answer":false}` + "\n" +
		`{"answer":false}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Confirm(ConfirmConfig{
		Message:  "Q",
		Validate: func(v any) error { return fmt.Errorf("must accept") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
	if !errors.Is(err, ErrValidation) {
		t.Fatalf("expected ErrValidation, got: %v", err)
	}
}

func TestConfirmCoerceFloat(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":1.0}`+"\n")
	defer cleanup()

	result, err := Confirm(ConfirmConfig{Message: "Q"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result {
		t.Fatal("1.0 should coerce to true")
	}
}

func TestConfirmDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":""}`+"\n")
	defer cleanup()

	result, err := Confirm(ConfirmConfig{Message: "Q", Default: true})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// empty string coerces to false (not in truthy list)
	if result != false {
		t.Fatal("empty string should coerce to false")
	}
}

// ── Text: validate + filter callbacks ──

func TestTextValidateAndFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"  HELLO  "}`+"\n")
	defer cleanup()

	result, err := Text(TextConfig{
		Message: "Q",
		Filter: func(s string) string {
			return s[2 : len(s)-2] // trim 2 chars each side
		},
		Validate: func(s string) error {
			if s != "HELLO" {
				return fmt.Errorf("expected HELLO")
			}
			return nil
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "HELLO" {
		t.Fatalf("expected 'HELLO', got %q", result)
	}
}

// ── Select: validate + filter ──

func TestSelectFilterApplied(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"a"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Filter:  func(v any) any { return v.(string) + "_filtered" },
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "a_filtered" {
		t.Fatalf("expected 'a_filtered', got %v", result)
	}
}

func TestSelectValidateRejects(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"a"}`+"\n")
	defer cleanup()

	_, err := Select(SelectConfig{
		Message:  "Q",
		Choices:  []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Validate: func(v any) error { return fmt.Errorf("nope") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

// ── Checkbox: validate + filter ──

func TestCheckboxFilterApplied(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a","b"]}`+"\n")
	defer cleanup()

	result, err := Checkbox(CheckboxConfig{
		Message: "Q",
		Choices: []ChoiceItem{
			Choice{Name: "A", Value: "a"},
			Choice{Name: "B", Value: "b"},
		},
		Filter: func(v any) any {
			if list, ok := v.([]any); ok {
				return list[:1] // keep only first
			}
			return v
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 1 || result[0] != "a" {
		t.Fatalf("filter should have kept only first item, got %v", result)
	}
}

func TestCheckboxValidateRejects(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a"]}`+"\n")
	defer cleanup()

	_, err := Checkbox(CheckboxConfig{
		Message:  "Q",
		Choices:  []ChoiceItem{Choice{Name: "A", Value: "a"}, Choice{Name: "B", Value: "b"}},
		Validate: func(v any) error { return fmt.Errorf("pick at least 2") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

// ── Number: validate + filter ──

func TestNumberFilterApplied(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":10}`+"\n")
	defer cleanup()

	result, err := Number(NumberConfig{
		Message: "Q",
		Filter:  func(v float64) float64 { return v * 2 },
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 20 {
		t.Fatalf("expected 20, got %v", result)
	}
}

func TestNumberValidateRejects(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":13}`+"\n")
	defer cleanup()

	_, err := Number(NumberConfig{
		Message:  "Q",
		Validate: func(v float64) error { return fmt.Errorf("unlucky") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

// ── Expand: filter + validate ──

func TestExpandFilterApplied(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"y"}`+"\n")
	defer cleanup()

	result, err := Expand(ExpandConfig{
		Message: "Q",
		Choices: []ExpandChoice{{Key: "y", Name: "Yes", Value: "yes"}},
		Filter:  func(v any) any { return "filtered_" + v.(string) },
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "filtered_yes" {
		t.Fatalf("expected 'filtered_yes', got %v", result)
	}
}

// ── Rawlist: by name, filter ──

func TestRawlistByName(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"Beta"}`+"\n")
	defer cleanup()

	result, err := Rawlist(RawlistConfig{
		Message: "Q",
		Choices: []ChoiceItem{
			Choice{Name: "Alpha", Value: "a"},
			Choice{Name: "Beta", Value: "b"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "b" {
		t.Fatalf("expected 'b', got %v", result)
	}
}

func TestRawlistFilterApplied(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":1}`+"\n")
	defer cleanup()

	result, err := Rawlist(RawlistConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Filter:  func(v any) any { return "f_" + v.(string) },
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "f_a" {
		t.Fatalf("expected 'f_a', got %v", result)
	}
}

// ── Search: filter + validate ──

func TestSearchFilterApplied(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"pg"}`+"\n")
	defer cleanup()

	result, err := Search(SearchConfig{
		Message: "Q",
		Source: func(term string) []ChoiceItem {
			return []ChoiceItem{Choice{Name: "PG", Value: "pg"}}
		},
		Filter: func(v any) any { return v.(string) + "sql" },
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "pgsql" {
		t.Fatalf("expected 'pgsql', got %v", result)
	}
}

// ── Path: validate ──

func TestPathValidateRejects(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"/bad"}`+"\n")
	defer cleanup()

	_, err := Path(PathConfig{
		Message:  "Q",
		Validate: func(s string) error { return fmt.Errorf("invalid") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

// ── Autocomplete: validate + default ──

func TestAutocompleteValidateRejects(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"bad"}`+"\n")
	defer cleanup()

	_, err := Autocomplete(AutocompleteConfig{
		Message:  "Q",
		Choices:  []string{"a", "b"},
		Validate: func(s string) error { return fmt.Errorf("nope") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

func TestAutocompleteDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	result, err := Autocomplete(AutocompleteConfig{
		Message: "Q",
		Choices: []string{"a"},
		Default: "fallback",
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "fallback" {
		t.Fatalf("expected 'fallback', got %q", result)
	}
}

// ── Editor: default on null ──

func TestEditorDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	result, err := Editor(EditorConfig{Message: "Q", Default: "template"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "template" {
		t.Fatalf("expected 'template', got %q", result)
	}
}

// ── MarshalJSON: direct test ──

func TestSeparatorMarshalJSONDirect(t *testing.T) {
	s := Separator{Text: `hello "world"`}
	data, err := s.MarshalJSON()
	if err != nil {
		t.Fatalf("MarshalJSON error: %v", err)
	}
	expected := `{"type":"separator","text":"hello \"world\""}`
	if string(data) != expected {
		t.Fatalf("expected %s, got %s", expected, data)
	}
}

// ── IsSelectable: all branches ──

func TestIsSelectableAllCases(t *testing.T) {
	if !IsSelectable(Choice{Name: "A", Value: "a"}) {
		t.Fatal("enabled choice should be selectable")
	}
	if IsSelectable(Choice{Name: "A", Value: "a", Disabled: true}) {
		t.Fatal("disabled=true should not be selectable")
	}
	if IsSelectable(Choice{Name: "A", Value: "a", Disabled: "reason"}) {
		t.Fatal("disabled=string should not be selectable")
	}
	if IsSelectable(Separator{}) {
		t.Fatal("separator should not be selectable")
	}
}

// ── visibleRange ──

func TestVisibleRange(t *testing.T) {
	start, end := visibleRange(0, 20, 10)
	if start != 0 || end != 10 {
		t.Fatalf("expected 0-10, got %d-%d", start, end)
	}

	start, end = visibleRange(15, 20, 10)
	if start != 10 || end != 20 {
		t.Fatalf("expected 10-20, got %d-%d", start, end)
	}

	start, end = visibleRange(5, 20, 10)
	if start != 0 || end != 10 {
		t.Fatalf("expected 0-10, got %d-%d", start, end)
	}

	start, end = visibleRange(3, 5, 10)
	if start != 0 || end != 5 {
		t.Fatalf("expected 0-5 when total < pageSize, got %d-%d", start, end)
	}
}

// ── IsAgentMode ──

func TestIsAgentModeHuman(t *testing.T) {
	t.Setenv("INQUIRER_AI_MODE", "human")
	if IsAgentMode() {
		t.Fatal("should be false when INQUIRER_AI_MODE=human")
	}
}

func TestIsAgentModeAgent(t *testing.T) {
	t.Setenv("INQUIRER_AI_MODE", "agent")
	if !IsAgentMode() {
		t.Fatal("should be true when INQUIRER_AI_MODE=agent")
	}
}

func TestIsAgentModeCaseInsensitive(t *testing.T) {
	t.Setenv("INQUIRER_AI_MODE", "AGENT")
	if !IsAgentMode() {
		t.Fatal("should be case insensitive")
	}
}
