package prompt

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

// ── Malformed JSON ──

func TestChaosGarbageJSON(t *testing.T) {
	types := []struct {
		name string
		run  func() error
	}{
		{"Text", func() error {
			r, w, cleanup := agentSetup(t, "not json\n")
			defer cleanup()
			_, err := Text(TextConfig{Message: "Q"})
			readOutput(r, w)
			return err
		}},
		{"Select", func() error {
			r, w, cleanup := agentSetup(t, "not json\n")
			defer cleanup()
			_, err := Select(SelectConfig{
				Message: "Q",
				Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
			})
			readOutput(r, w)
			return err
		}},
		{"Confirm", func() error {
			r, w, cleanup := agentSetup(t, "not json\n")
			defer cleanup()
			_, err := Confirm(ConfirmConfig{Message: "Q"})
			readOutput(r, w)
			return err
		}},
		{"Number", func() error {
			r, w, cleanup := agentSetup(t, "not json\n")
			defer cleanup()
			_, err := Number(NumberConfig{Message: "Q"})
			readOutput(r, w)
			return err
		}},
	}

	for _, tc := range types {
		t.Run(tc.name, func(t *testing.T) {
			err := tc.run()
			if err == nil {
				t.Fatalf("%s: expected error for garbage JSON", tc.name)
			}
			if !errors.Is(err, ErrInvalidJSON) {
				t.Fatalf("%s: expected ErrInvalidJSON, got: %v", tc.name, err)
			}
		})
	}
}

// ── Unicode bomb ──

func TestChaosUnicodeBomb(t *testing.T) {
	inputs := []struct {
		name  string
		value string
	}{
		{"emoji", "\U0001F680\U0001F31F\U0001F4A5"},
		{"CJK", "你好世界"},
		{"RTL", "مرحبا"},
		{"zero-width", "a\u200Bb\u200Cc\u200Dd\uFEFFe"},
		{"mixed", "\U0001F602你م\u200Bä"},
	}

	for _, tc := range inputs {
		t.Run(tc.name, func(t *testing.T) {
			// Use encoding/json to properly escape the value.
			wrapper := map[string]string{"answer": tc.value}
			data, err := json.Marshal(wrapper)
			if err != nil {
				t.Fatalf("failed to marshal: %v", err)
			}
			jsonInput := string(data) + "\n"

			r, w, cleanup := agentSetup(t, jsonInput)
			defer cleanup()

			result, err := Text(TextConfig{Message: "Q"})
			readOutput(r, w)

			if err != nil {
				t.Fatalf("unexpected error for %s input: %v", tc.name, err)
			}
			if result != tc.value {
				t.Fatalf("unicode round-trip failed for %s: expected %q, got %q", tc.name, tc.value, result)
			}
		})
	}
}

// ── Huge input ──

func TestChaosHugeInput(t *testing.T) {
	huge := strings.Repeat("X", 100*1024) // 100 KB
	// The string is pure ASCII, safe to embed directly.
	jsonInput := `{"answer":"` + huge + `"}` + "\n"

	r, w, cleanup := agentSetup(t, jsonInput)
	defer cleanup()

	result, err := Text(TextConfig{Message: "Q"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error for huge input: %v", err)
	}
	if len(result) != 100*1024 {
		t.Fatalf("expected 102400 chars, got %d", len(result))
	}
}

// ── Nested JSON injection ──

func TestChaosJSONInject(t *testing.T) {
	// The answer value is a string that looks like JSON — it should stay a string.
	jsonInput := `{"answer":"{\"injected\": true}"}` + "\n"

	r, w, cleanup := agentSetup(t, jsonInput)
	defer cleanup()

	result, err := Text(TextConfig{Message: "Q"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	expected := `{"injected": true}`
	if result != expected {
		t.Fatalf("JSON injection: expected %q, got %q", expected, result)
	}
}

// ── Null answers for each type ──

func TestChaosNullAnswers(t *testing.T) {
	t.Run("TextNull", func(t *testing.T) {
		r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
		defer cleanup()

		result, err := Text(TextConfig{Message: "Q"})
		readOutput(r, w)

		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if result != "" {
			t.Fatalf("expected empty string for null text, got %q", result)
		}
	})

	t.Run("ConfirmNull", func(t *testing.T) {
		r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
		defer cleanup()

		result, err := Confirm(ConfirmConfig{Message: "Q"})
		readOutput(r, w)

		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if result != false {
			t.Fatalf("expected false for null confirm, got %v", result)
		}
	})

	t.Run("NumberNullWithDefault", func(t *testing.T) {
		r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
		defer cleanup()

		def := 99.0
		result, err := Number(NumberConfig{Message: "Q", Default: &def})
		readOutput(r, w)

		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if result != 99 {
			t.Fatalf("expected 99 for null number with default, got %v", result)
		}
	})
}

// ── Wrong type for checkbox ──

func TestChaosWrongTypeForCheckbox(t *testing.T) {
	// Send a string instead of an array.
	r, w, cleanup := agentSetup(t, `{"answer":"not-a-list"}`+"\n")
	defer cleanup()

	_, err := Checkbox(CheckboxConfig{
		Message: "Q",
		Choices: []ChoiceItem{
			Choice{Name: "A", Value: "a"},
			Choice{Name: "B", Value: "b"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error when checkbox receives a string instead of array")
	}
	if !errors.Is(err, ErrValidation) {
		t.Fatalf("expected ErrValidation, got: %v", err)
	}
}

// ── Empty answer for select ──

func TestChaosEmptyAnswer(t *testing.T) {
	// Send empty string to a Select with choices — should fail validation.
	r, w, cleanup := agentSetup(t, `{"answer":""}`+"\n")
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Q",
		Choices: []ChoiceItem{
			Choice{Name: "Alpha", Value: "a"},
			Choice{Name: "Beta", Value: "b"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for empty answer on select")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}
