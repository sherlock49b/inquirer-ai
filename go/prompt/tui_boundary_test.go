package prompt

import (
	"errors"
	"fmt"
	"strings"
	"testing"
)

// --- TUI Boundary Tests (Agent Mode) ---

// 1. Single choice select: only one choice offered, agent picks it.
func TestTuiBoundarySingleChoiceSelect(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"only"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Pick one",
		Choices: []ChoiceItem{
			Choice{Name: "Only Option", Value: "only"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "only" {
		t.Fatalf("expected 'only', got %v", result)
	}
}

// 2. Large choice list: 100+ choices; verify correct selection.
func TestTuiBoundaryLargeChoiceList(t *testing.T) {
	var choices []ChoiceItem
	for i := 0; i < 150; i++ {
		choices = append(choices, Choice{
			Name:  fmt.Sprintf("Item-%03d", i),
			Value: fmt.Sprintf("val-%03d", i),
		})
	}

	// Select item near the end to exercise pagination boundaries.
	r, w, cleanup := agentSetup(t, `{"answer":"val-142"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message:  "Pick from many",
		Choices:  choices,
		PageSize: 10,
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "val-142" {
		t.Fatalf("expected 'val-142', got %v", result)
	}
}

// 3. Disabled choices are filtered from selectable agent choices.
func TestTuiBoundaryDisabledFiltered(t *testing.T) {
	// Attempt to select a disabled choice: should fail after 3 retries.
	input := strings.Repeat(`{"answer":"disabled-val"}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "Enabled", Value: "enabled-val"},
			Choice{Name: "Disabled", Value: "disabled-val", Disabled: true},
			Choice{Name: "Also Disabled", Value: "also-disabled", Disabled: "reason: not available"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error when selecting a disabled choice")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}

// 4. Separator is not in selectable agent choices.
func TestTuiBoundarySeparatorNotSelectable(t *testing.T) {
	// Try selecting the separator text: should fail after 3 retries.
	input := strings.Repeat(`{"answer":"────────"}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "Alpha", Value: "a"},
			Separator{},
			Choice{Name: "Beta", Value: "b"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error when selecting a separator")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}

// 5. Checkbox required=true, empty answer returns error.
func TestTuiBoundaryCheckboxRequiredEmpty(t *testing.T) {
	input := strings.Repeat(`{"answer":[]}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Checkbox(CheckboxConfig{
		Message:  "Select features",
		Required: true,
		Choices: []ChoiceItem{
			Choice{Name: "Docker", Value: "docker"},
			Choice{Name: "CI", Value: "ci"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for empty checkbox with required=true")
	}
	if !errors.Is(err, ErrValidation) {
		t.Fatalf("expected ErrValidation, got: %v", err)
	}
	if !strings.Contains(err.Error(), "At least one choice is required") {
		t.Fatalf("expected required message, got: %v", err)
	}
}

// 5b. Checkbox required=true with custom RequiredMessage.
func TestTuiBoundaryCheckboxRequiredCustomMsg(t *testing.T) {
	input := strings.Repeat(`{"answer":[]}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Checkbox(CheckboxConfig{
		Message:         "Select features",
		Required:        true,
		RequiredMessage: "You must pick something!",
		Choices: []ChoiceItem{
			Choice{Name: "A", Value: "a"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for empty checkbox with custom required message")
	}
	if !strings.Contains(err.Error(), "You must pick something!") {
		t.Fatalf("expected custom required message, got: %v", err)
	}
}

// 6. Checkbox all selected: select every choice.
func TestTuiBoundaryCheckboxAllSelected(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a","b","c"]}`+"\n")
	defer cleanup()

	result, err := Checkbox(CheckboxConfig{
		Message: "Select all",
		Choices: []ChoiceItem{
			Choice{Name: "A", Value: "a"},
			Choice{Name: "B", Value: "b"},
			Choice{Name: "C", Value: "c"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 3 {
		t.Fatalf("expected 3 items selected, got %d", len(result))
	}
	for i, expected := range []string{"a", "b", "c"} {
		if result[i] != expected {
			t.Fatalf("result[%d]: expected %q, got %v", i, expected, result[i])
		}
	}
}

// 7. Duplicate choice values: first match wins.
func TestTuiBoundaryDuplicateChoiceValues(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"dup"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "dup"},
			Choice{Name: "Second", Value: "dup"},
			Choice{Name: "Third", Value: "other"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// The agent loop breaks on the first match, so value should be "dup".
	if result != "dup" {
		t.Fatalf("expected 'dup', got %v", result)
	}
}

// 7b. Duplicate values in checkbox: each occurrence matched once.
func TestTuiBoundaryDuplicateChoiceValuesCheckbox(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["dup","other"]}`+"\n")
	defer cleanup()

	result, err := Checkbox(CheckboxConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "dup"},
			Choice{Name: "Second", Value: "dup"},
			Choice{Name: "Third", Value: "other"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 2 {
		t.Fatalf("expected 2 items, got %d", len(result))
	}
}

// 8. Unicode choice names: CJK, emoji, diacritics.
func TestTuiBoundaryUnicodeChoiceNames(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"日本語"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "言語を選択",
		Choices: []ChoiceItem{
			Choice{Name: "中文", Value: "中文"},
			Choice{Name: "日本語", Value: "日本語"},
			Choice{Name: "한국어", Value: "한국어"},
			Choice{Name: "café", Value: "café"},
			Choice{Name: "🚀🌍", Value: "emoji"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "日本語" {
		t.Fatalf("expected '日本語', got %v", result)
	}
}

// 8b. Unicode emoji in checkbox.
func TestTuiBoundaryUnicodeCheckbox(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["🚀🌍","café"]}`+"\n")
	defer cleanup()

	result, err := Checkbox(CheckboxConfig{
		Message: "Pick emojis",
		Choices: []ChoiceItem{
			Choice{Name: "🚀🌍", Value: "🚀🌍"},
			Choice{Name: "café", Value: "café"},
			Choice{Name: "plain", Value: "plain"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 2 {
		t.Fatalf("expected 2 items, got %d", len(result))
	}
	if result[0] != "🚀🌍" {
		t.Fatalf("expected first item '🚀🌍', got %v", result[0])
	}
}

// 9. Choice with empty string name: matched by value.
func TestTuiBoundaryEmptyStringName(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"empty-val"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "", Value: "empty-val"},
			Choice{Name: "Normal", Value: "normal"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "empty-val" {
		t.Fatalf("expected 'empty-val', got %v", result)
	}
}

// 9b. Choice with empty string value: matched by name.
func TestTuiBoundaryEmptyStringValue(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"Has Name"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "Has Name", Value: ""},
			Choice{Name: "Normal", Value: "normal"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "" {
		t.Fatalf("expected empty string value, got %v", result)
	}
}

// 10. Rawlist with out-of-range index: should error.
func TestTuiBoundaryRawlistOutOfRange(t *testing.T) {
	input := strings.Repeat(`{"answer":99}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Rawlist(RawlistConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "1st"},
			Choice{Name: "Second", Value: "2nd"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for out-of-range rawlist index")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}

// 10b. Rawlist with zero index (boundary: indices are 1-based).
func TestTuiBoundaryRawlistZeroIndex(t *testing.T) {
	input := strings.Repeat(`{"answer":0}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Rawlist(RawlistConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "1st"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for zero rawlist index")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}

// 10c. Rawlist with negative index.
func TestTuiBoundaryRawlistNegativeIndex(t *testing.T) {
	input := strings.Repeat(`{"answer":-1}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Rawlist(RawlistConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "1st"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for negative rawlist index")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}

// Additional boundary tests for visibleRange pagination logic.

func TestTuiBoundaryVisibleRangeSmallList(t *testing.T) {
	// When total < pageSize, the entire list should be visible.
	start, end := visibleRange(0, 3, 10)
	if start != 0 || end != 3 {
		t.Fatalf("expected [0,3), got [%d,%d)", start, end)
	}
}

func TestTuiBoundaryVisibleRangeCursorAtEnd(t *testing.T) {
	// Cursor at the last item of a 100-item list with pageSize 10.
	start, end := visibleRange(99, 100, 10)
	if start != 90 || end != 100 {
		t.Fatalf("expected [90,100), got [%d,%d)", start, end)
	}
}

func TestTuiBoundaryVisibleRangeCursorAtStart(t *testing.T) {
	start, end := visibleRange(0, 100, 10)
	if start != 0 || end != 10 {
		t.Fatalf("expected [0,10), got [%d,%d)", start, end)
	}
}

func TestTuiBoundaryVisibleRangeMiddle(t *testing.T) {
	// Cursor in the middle: window should center around cursor.
	start, end := visibleRange(50, 100, 10)
	if start != 45 || end != 55 {
		t.Fatalf("expected [45,55), got [%d,%d)", start, end)
	}
}

// Select with Disabled as a string reason (not just bool).
func TestTuiBoundaryDisabledWithStringReason(t *testing.T) {
	input := strings.Repeat(`{"answer":"disabled-str"}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "OK", Value: "ok"},
			Choice{Name: "Nope", Value: "disabled-str", Disabled: "not available yet"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error when selecting a choice disabled with string reason")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}

// Checkbox with mix of disabled, separators, and valid choices.
func TestTuiBoundaryCheckboxMixedChoices(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a","c"]}`+"\n")
	defer cleanup()

	result, err := Checkbox(CheckboxConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "A", Value: "a"},
			Separator{Text: "---"},
			Choice{Name: "B", Value: "b", Disabled: true},
			Choice{Name: "C", Value: "c"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 2 {
		t.Fatalf("expected 2 items, got %d", len(result))
	}
	if result[0] != "a" || result[1] != "c" {
		t.Fatalf("expected [a, c], got %v", result)
	}
}

// Rawlist valid boundary: exact max index.
func TestTuiBoundaryRawlistExactMaxIndex(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":3}`+"\n")
	defer cleanup()

	result, err := Rawlist(RawlistConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "1st"},
			Choice{Name: "Second", Value: "2nd"},
			Choice{Name: "Third", Value: "3rd"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "3rd" {
		t.Fatalf("expected '3rd', got %v", result)
	}
}
