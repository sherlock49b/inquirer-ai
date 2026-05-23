package prompt

import (
	"fmt"
	"strings"
	"testing"
)

func TestSelectEmptyChoices(t *testing.T) {
	_, err := Select(SelectConfig{Message: "Pick", Choices: nil})
	if err == nil {
		t.Fatal("expected error for empty choices")
	}
}

func TestCheckboxEmptyChoices(t *testing.T) {
	_, err := Checkbox(CheckboxConfig{Message: "Pick", Choices: nil})
	if err == nil {
		t.Fatal("expected error for empty choices")
	}
}

func TestExpandEmptyChoices(t *testing.T) {
	_, err := Expand(ExpandConfig{Message: "Pick", Choices: nil})
	if err == nil {
		t.Fatal("expected error for empty choices")
	}
}

func TestExpandDuplicateKeys(t *testing.T) {
	_, err := Expand(ExpandConfig{
		Message: "Pick",
		Choices: []ExpandChoice{
			{Key: "y", Name: "Yes", Value: true},
			{Key: "Y", Name: "Yep", Value: true},
		},
	})
	if err == nil {
		t.Fatal("expected error for duplicate keys")
	}
}

func TestRawlistEmptyChoices(t *testing.T) {
	_, err := Rawlist(RawlistConfig{Message: "Pick", Choices: nil})
	if err == nil {
		t.Fatal("expected error for empty choices")
	}
}

func TestSelectDisabledChoiceRejected(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"d"}`+"\n")
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "OK", Value: "ok"},
			Choice{Name: "Disabled", Value: "d", Disabled: true},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for disabled choice")
	}
}

func TestCheckboxRejectsDisabled(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["d"]}`+"\n")
	defer cleanup()

	_, err := Checkbox(CheckboxConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "OK", Value: "ok"},
			Choice{Name: "Disabled", Value: "d", Disabled: true},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for disabled choice in checkbox")
	}
}

func TestCheckboxNonListRejected(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"not-a-list"}`+"\n")
	defer cleanup()

	_, err := Checkbox(CheckboxConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "A", Value: "a"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for non-list answer in checkbox")
	}
}

func TestTextValidationFails(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":""}`+"\n")
	defer cleanup()

	_, err := Text(TextConfig{
		Message:  "Name?",
		Validate: func(s string) error { return fmt.Errorf("cannot be empty") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

func TestTextFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"  hello  "}`+"\n")
	defer cleanup()

	result, err := Text(TextConfig{
		Message: "Name?",
		Filter:  strings.TrimSpace,
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "hello" {
		t.Fatalf("expected 'hello', got %q", result)
	}
}

func TestNumberMinViolation(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":3}`+"\n")
	defer cleanup()

	min := 5.0
	_, err := Number(NumberConfig{Message: "Num?", Min: &min})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected min violation error")
	}
}

func TestNumberMaxViolation(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":100}`+"\n")
	defer cleanup()

	max := 50.0
	_, err := Number(NumberConfig{Message: "Num?", Max: &max})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected max violation error")
	}
}

func TestNumberRejectsNonFloat(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":3.5}`+"\n")
	defer cleanup()

	_, err := Number(NumberConfig{Message: "Num?", FloatAllowed: false})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for float when not allowed")
	}
}

func TestNumberDefaultOnNull(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	def := 42.0
	result, err := Number(NumberConfig{Message: "Num?", Default: &def})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 42 {
		t.Fatalf("expected 42, got %v", result)
	}
}

func TestPasswordValidation(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"ab"}`+"\n")
	defer cleanup()

	_, err := Password(PasswordConfig{
		Message:  "Token?",
		Validate: func(s string) error { return fmt.Errorf("too short") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

func TestPathValidation(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"/nonexistent"}`+"\n")
	defer cleanup()

	_, err := Path(PathConfig{
		Message:  "Path?",
		Validate: func(s string) error { return fmt.Errorf("bad path") },
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
}

func TestMoveCursorWraps(t *testing.T) {
	selectable := []int{0, 2, 4}
	result := moveCursor(4, 1, selectable, true)
	if result != 0 {
		t.Fatalf("expected wrap to 0, got %d", result)
	}
	result = moveCursor(0, -1, selectable, true)
	if result != 4 {
		t.Fatalf("expected wrap to 4, got %d", result)
	}
}

func TestMoveCursorClamps(t *testing.T) {
	selectable := []int{0, 2, 4}
	result := moveCursor(4, 1, selectable, false)
	if result != 4 {
		t.Fatalf("expected clamp at 4, got %d", result)
	}
	result = moveCursor(0, -1, selectable, false)
	if result != 0 {
		t.Fatalf("expected clamp at 0, got %d", result)
	}
}

func TestMoveCursorInvalidResets(t *testing.T) {
	selectable := []int{1, 3}
	result := moveCursor(99, 1, selectable, true)
	if result != 1 {
		t.Fatalf("expected reset to 1, got %d", result)
	}
}

func TestSelectByName(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"Alpha"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "Alpha", Value: "a"},
			Choice{Name: "Beta", Value: "b"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "a" {
		t.Fatalf("expected 'a', got %v", result)
	}
}

func TestUnicodeChoices(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"🍌"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "🍎", Value: "🍎"},
			Choice{Name: "🍌", Value: "🍌"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "🍌" {
		t.Fatalf("expected 🍌, got %v", result)
	}
}

func TestLongTextInput(t *testing.T) {
	long := strings.Repeat("x", 100000)
	r, w, cleanup := agentSetup(t, `{"answer":"`+long+`"}`+"\n")
	defer cleanup()

	result, err := Text(TextConfig{Message: "Q"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 100000 {
		t.Fatalf("expected 100000 chars, got %d", len(result))
	}
}

func TestConfirmStringCoercion(t *testing.T) {
	for _, tc := range []struct {
		input    string
		expected bool
	}{
		{`"yes"`, true},
		{`"no"`, false},
		{`"Y"`, true},
		{`"true"`, true},
		{`"false"`, false},
		{`"1"`, true},
		{`"0"`, false},
	} {
		r, w, cleanup := agentSetup(t, `{"answer":`+tc.input+`}`+"\n")
		result, err := Confirm(ConfirmConfig{Message: "Q"})
		readOutput(r, w)
		cleanup()

		if err != nil {
			t.Fatalf("input %s: unexpected error: %v", tc.input, err)
		}
		if result != tc.expected {
			t.Fatalf("input %s: expected %v, got %v", tc.input, tc.expected, result)
		}
	}
}
