package prompt

import (
	"errors"
	"testing"
)

// ── Agent error paths: EOF, bad JSON, missing answer for each prompt type ──

func TestConfirmAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Confirm(ConfirmConfig{Message: "Q"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestSelectAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Select(SelectConfig{Message: "Q", Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}}})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestCheckboxAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Checkbox(CheckboxConfig{Message: "Q", Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}}})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestNumberAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Number(NumberConfig{Message: "Q"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestPasswordAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Password(PasswordConfig{Message: "Q"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestExpandAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Expand(ExpandConfig{Message: "Q", Choices: []ExpandChoice{{Key: "y", Name: "Yes", Value: true}}})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestRawlistAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Rawlist(RawlistConfig{Message: "Q", Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}}})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestEditorAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Editor(EditorConfig{Message: "Q"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestPathAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Path(PathConfig{Message: "Q"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestAutocompleteAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Autocomplete(AutocompleteConfig{Message: "Q", Choices: []string{"a"}})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

func TestSearchAgentEOF(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()
	_, err := Search(SearchConfig{
		Message: "Q",
		Source:  func(string) []ChoiceItem { return []ChoiceItem{Choice{Name: "A", Value: "a"}} },
	})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error on EOF")
	}
}

// ── Rawlist: out-of-range index ──

func TestRawlistOutOfRangeIndex(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":0}`+"\n")
	defer cleanup()
	_, err := Rawlist(RawlistConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
	})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for index 0")
	}
}

func TestRawlistNegativeIndex(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":-1}`+"\n")
	defer cleanup()
	_, err := Rawlist(RawlistConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
	})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for negative index")
	}
}

// ── Expand: invalid key ──

func TestExpandInvalidKey(t *testing.T) {
	// Provide 3 answers for retry loop.
	input := `{"answer":"z"}` + "\n" +
		`{"answer":"z"}` + "\n" +
		`{"answer":"z"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()
	_, err := Expand(ExpandConfig{
		Message: "Q",
		Choices: []ExpandChoice{{Key: "y", Name: "Yes", Value: true}},
	})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for invalid key")
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
}

// ── Number: string that's not a number ──

func TestNumberInvalidString(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"abc"}`+"\n")
	defer cleanup()
	_, err := Number(NumberConfig{Message: "Q"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for non-numeric string")
	}
}

// ── Number: bool rejected ──

func TestNumberBoolRejected(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":true}`+"\n")
	defer cleanup()
	_, err := Number(NumberConfig{Message: "Q"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for bool input")
	}
}

// ── Checkbox: non-list answer ──

func TestCheckboxStringAnswer(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"not a list"}`+"\n")
	defer cleanup()
	_, err := Checkbox(CheckboxConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
	})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for string answer")
	}
}

// ── parseChoices: Separator default text ──

func TestParseChoicesDefaultSeparator(t *testing.T) {
	items := parseChoices([]ChoiceItem{Separator{}})
	if len(items) != 1 {
		t.Fatalf("expected 1 item, got %d", len(items))
	}
	if items[0].name != "────────" {
		t.Fatalf("expected default separator text, got %q", items[0].name)
	}
}

// ── marshalItems: Choice with all optional fields ──

func TestMarshalItemsFullChoice(t *testing.T) {
	items := marshalItems([]ChoiceItem{
		Choice{Name: "PG", Value: "pg", Short: "P", Description: "Relational DB", Disabled: "not ready"},
	})
	m := items[0].(map[string]any)
	if m["short"] != "P" {
		t.Fatalf("expected short=P, got %v", m["short"])
	}
	if m["description"] != "Relational DB" {
		t.Fatalf("expected description, got %v", m["description"])
	}
	if m["disabled"] != "not ready" {
		t.Fatalf("expected disabled='not ready', got %v", m["disabled"])
	}
}

func TestMarshalItemsSeparatorDefault(t *testing.T) {
	items := marshalItems([]ChoiceItem{Separator{}})
	m := items[0].(map[string]any)
	if m["text"] != "────────" {
		t.Fatalf("expected default separator text, got %v", m["text"])
	}
}
