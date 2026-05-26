package prompt

import (
	"encoding/json"
	"fmt"
	"testing"
)

// ────────────────────────────────────────────────────────────────────────────
// 1. Handshake format
// ────────────────────────────────────────────────────────────────────────────

func TestProtocolHandshakeFormat(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"ok"}`+"\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Q?"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 1 {
		t.Fatal("expected at least 1 output line (handshake)")
	}

	hs := lines[0]

	// Required handshake fields
	checks := []struct {
		key string
		val any
	}{
		{"kind", "handshake"},
		{"protocol", "inquirer-ai"},
		{"version", Version},
		{"format", "jsonl"},
		{"interaction", "sequential"},
	}
	for _, c := range checks {
		got, ok := hs[c.key]
		if !ok {
			t.Fatalf("handshake missing field %q", c.key)
		}
		if got != c.val {
			t.Fatalf("handshake %q: expected %v, got %v", c.key, c.val, got)
		}
	}

	// total must be present (value may be nil/null)
	if _, ok := hs["total"]; !ok {
		t.Fatal("handshake missing 'total' field")
	}

	// description must be a non-empty string
	desc, ok := hs["description"].(string)
	if !ok || desc == "" {
		t.Fatal("handshake 'description' must be a non-empty string")
	}

	// example_response must be present and contain "answer" key
	er, ok := hs["example_response"].(map[string]any)
	if !ok {
		t.Fatal("handshake 'example_response' must be an object")
	}
	if _, ok := er["answer"]; !ok {
		t.Fatal("handshake 'example_response' must contain 'answer' key")
	}
}

// ────────────────────────────────────────────────────────────────────────────
// 2. Prompt format per type
// ────────────────────────────────────────────────────────────────────────────

func TestProtocolPromptFormatText(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"val"}`+"\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Enter name", Default: "world"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "input", "Enter name")
	if p["default"] != "world" {
		t.Fatalf("expected default='world', got %v", p["default"])
	}
}

func TestProtocolPromptFormatSelect(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"a"}`+"\n")
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Pick one",
		Choices: []ChoiceItem{
			Choice{Name: "Alpha", Value: "a"},
			Choice{Name: "Beta", Value: "b"},
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "select", "Pick one")
	choices, ok := p["choices"].([]any)
	if !ok || len(choices) == 0 {
		t.Fatal("select prompt must have non-empty 'choices' array")
	}
	// Verify first choice has name and value
	first, ok := choices[0].(map[string]any)
	if !ok {
		t.Fatal("choice item must be an object")
	}
	if first["name"] != "Alpha" || first["value"] != "a" {
		t.Fatalf("unexpected first choice: %v", first)
	}
}

func TestProtocolPromptFormatCheckbox(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["x"]}`+"\n")
	defer cleanup()

	_, err := Checkbox(CheckboxConfig{
		Message: "Multi select",
		Choices: []ChoiceItem{
			Choice{Name: "X", Value: "x"},
			Choice{Name: "Y", Value: "y"},
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "checkbox", "Multi select")
	choices, ok := p["choices"].([]any)
	if !ok || len(choices) == 0 {
		t.Fatal("checkbox prompt must have non-empty 'choices' array")
	}
}

func TestProtocolPromptFormatConfirm(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":true}`+"\n")
	defer cleanup()

	_, err := Confirm(ConfirmConfig{Message: "Proceed?", Default: true})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "confirm", "Proceed?")
	if p["default"] != true {
		t.Fatalf("expected default=true, got %v", p["default"])
	}
}

func TestProtocolPromptFormatNumber(t *testing.T) {
	min := 0.0
	max := 100.0
	r, w, cleanup := agentSetup(t, `{"answer":42}`+"\n")
	defer cleanup()

	_, err := Number(NumberConfig{
		Message: "Port?",
		Min:     &min,
		Max:     &max,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "number", "Port?")
	if p["min"] != min {
		t.Fatalf("expected min=%v, got %v", min, p["min"])
	}
	if p["max"] != max {
		t.Fatalf("expected max=%v, got %v", max, p["max"])
	}
}

func TestProtocolPromptFormatPassword(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"secret"}`+"\n")
	defer cleanup()

	_, err := Password(PasswordConfig{Message: "Token?", Mask: "#"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "password", "Token?")
	if p["mask"] != "#" {
		t.Fatalf("expected mask='#', got %v", p["mask"])
	}
}

func TestProtocolPromptFormatEditor(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"edited"}`+"\n")
	defer cleanup()

	_, err := Editor(EditorConfig{Message: "Edit", Default: "draft", Postfix: ".md"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "editor", "Edit")
	if p["default"] != "draft" {
		t.Fatalf("expected default='draft', got %v", p["default"])
	}
	if p["postfix"] != ".md" {
		t.Fatalf("expected postfix='.md', got %v", p["postfix"])
	}
}

func TestProtocolPromptFormatExpand(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"y"}`+"\n")
	defer cleanup()

	_, err := Expand(ExpandConfig{
		Message: "Action?",
		Choices: []ExpandChoice{
			{Key: "y", Name: "Yes", Value: "yes"},
			{Key: "n", Name: "No", Value: "no"},
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "expand", "Action?")
	choices, ok := p["choices"].([]any)
	if !ok || len(choices) == 0 {
		t.Fatal("expand prompt must have non-empty 'choices' array")
	}
	first, ok := choices[0].(map[string]any)
	if !ok {
		t.Fatal("expand choice must be an object")
	}
	if first["key"] != "y" || first["name"] != "Yes" {
		t.Fatalf("unexpected expand choice: %v", first)
	}
}

func TestProtocolPromptFormatRawlist(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":1}`+"\n")
	defer cleanup()

	_, err := Rawlist(RawlistConfig{
		Message: "Pick number",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "1st"},
			Choice{Name: "Second", Value: "2nd"},
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "rawlist", "Pick number")
	choices, ok := p["choices"].([]any)
	if !ok || len(choices) == 0 {
		t.Fatal("rawlist prompt must have non-empty 'choices' array")
	}
}

func TestProtocolPromptFormatPath(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"/tmp"}`+"\n")
	defer cleanup()

	_, err := Path(PathConfig{
		Message:         "Dir?",
		Default:         "/home",
		OnlyDirectories: true,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "path", "Dir?")
	if p["default"] != "/home" {
		t.Fatalf("expected default='/home', got %v", p["default"])
	}
	if p["only_directories"] != true {
		t.Fatalf("expected only_directories=true, got %v", p["only_directories"])
	}
}

func TestProtocolPromptFormatAutocomplete(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"go"}`+"\n")
	defer cleanup()

	_, err := Autocomplete(AutocompleteConfig{
		Message: "Lang?",
		Choices: []string{"go", "rust", "python"},
		Default: "go",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "autocomplete", "Lang?")
	if p["default"] != "go" {
		t.Fatalf("expected default='go', got %v", p["default"])
	}
	choices, ok := p["choices"].([]any)
	if !ok || len(choices) != 3 {
		t.Fatalf("expected 3 choices, got %v", p["choices"])
	}
}

func TestProtocolPromptFormatSearch(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"pg"}`+"\n")
	defer cleanup()

	_, err := Search(SearchConfig{
		Message: "DB?",
		Source: func(term string) []ChoiceItem {
			return []ChoiceItem{
				Choice{Name: "PostgreSQL", Value: "pg"},
				Choice{Name: "MySQL", Value: "mysql"},
			}
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	assertPromptBase(t, p, "search", "DB?")
	if p["searchable"] != true {
		t.Fatalf("expected searchable=true, got %v", p["searchable"])
	}
	choices, ok := p["choices"].([]any)
	if !ok || len(choices) == 0 {
		t.Fatal("search prompt must have non-empty 'choices' array")
	}
}

// ────────────────────────────────────────────────────────────────────────────
// 3. Validation error format
// ────────────────────────────────────────────────────────────────────────────

func TestProtocolValidationErrorFormat(t *testing.T) {
	// First answer fails validation, second succeeds.
	// AgentPromptWithRetry retries up to 3 times.
	r, w, cleanup := agentSetup(t, `{"answer":""}`+"\n"+`{"answer":"valid"}`+"\n")
	defer cleanup()

	_, err := Text(TextConfig{
		Message: "Name?",
		Validate: func(s string) error {
			if s == "" {
				return fmt.Errorf("cannot be empty")
			}
			return nil
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)

	// Expect: handshake, prompt, validation_error, prompt (retry), ...
	foundValidationError := false
	for _, line := range lines {
		if line["kind"] == "validation_error" {
			foundValidationError = true
			msg, ok := line["message"].(string)
			if !ok || msg == "" {
				t.Fatal("validation_error must have a non-empty 'message' string")
			}
			break
		}
	}
	if !foundValidationError {
		t.Fatal("expected a validation_error JSONL line in output")
	}
}

func TestProtocolValidationErrorHasKindAndMessage(t *testing.T) {
	// Send three bad answers to exhaust retries.
	input := `{"answer":"bad"}` + "\n" +
		`{"answer":"bad"}` + "\n" +
		`{"answer":"bad"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Text(TextConfig{
		Message: "X?",
		Validate: func(s string) error {
			return fmt.Errorf("always reject")
		},
	})
	// We expect an error since all 3 retries failed.
	if err == nil {
		t.Fatal("expected error when all retries are exhausted")
	}
	lines := readOutput(r, w)

	validationErrors := 0
	for _, line := range lines {
		if line["kind"] == "validation_error" {
			validationErrors++
			if _, ok := line["message"].(string); !ok {
				t.Fatal("validation_error must have 'message' field")
			}
		}
	}
	// With 3 attempts and max 3 retries, we expect 2 validation_error messages
	// (first two failures send validation_error, third failure returns error).
	if validationErrors != 2 {
		t.Fatalf("expected 2 validation_error lines, got %d", validationErrors)
	}
}

// ────────────────────────────────────────────────────────────────────────────
// 4. Answer extraction
// ────────────────────────────────────────────────────────────────────────────

func TestContractAnswerExtractionString(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"hello"}`+"\n")
	defer cleanup()

	result, err := Text(TextConfig{Message: "Q?"})
	readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "hello" {
		t.Fatalf("expected 'hello', got %q", result)
	}
}

func TestContractAnswerExtractionNumber(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":3.14}`+"\n")
	defer cleanup()

	result, err := Number(NumberConfig{Message: "N?", FloatAllowed: true})
	readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 3.14 {
		t.Fatalf("expected 3.14, got %v", result)
	}
}

func TestContractAnswerExtractionBool(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":false}`+"\n")
	defer cleanup()

	result, err := Confirm(ConfirmConfig{Message: "C?"})
	readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != false {
		t.Fatalf("expected false, got %v", result)
	}
}

func TestContractAnswerExtractionList(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a","c"]}`+"\n")
	defer cleanup()

	result, err := Checkbox(CheckboxConfig{
		Message: "C?",
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
	if len(result) != 2 {
		t.Fatalf("expected 2 items, got %d", len(result))
	}
	if result[0] != "a" || result[1] != "c" {
		t.Fatalf("unexpected result: %v", result)
	}
}

func TestContractAnswerExtractionNull(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	result, err := Text(TextConfig{Message: "Q?", Default: "fallback"})
	readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "fallback" {
		t.Fatalf("expected 'fallback', got %q", result)
	}
}

func TestContractAnswerExtractionMissingKey(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"value":"oops"}`+"\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Q?"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for missing 'answer' key")
	}
}

func TestContractAnswerExtractionInvalidJSON(t *testing.T) {
	r, w, cleanup := agentSetup(t, "this is not json\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Q?"})
	readOutput(r, w)
	if err == nil {
		t.Fatal("expected error for invalid JSON input")
	}
}

func TestContractHandshakeAckSkipped(t *testing.T) {
	// Agent may send a handshake_ack before the real answer.
	input := `{"kind":"handshake_ack"}` + "\n" + `{"answer":"real"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	result, err := Text(TextConfig{Message: "Q?"})
	readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "real" {
		t.Fatalf("expected 'real', got %q", result)
	}
}

// ────────────────────────────────────────────────────────────────────────────
// 5. Fuzz test: answer extraction from random bytes
// ────────────────────────────────────────────────────────────────────────────

func FuzzAnswerExtract(f *testing.F) {
	f.Add([]byte(`{"answer":"hello"}`))
	f.Add([]byte(`{"answer":42}`))
	f.Add([]byte(`{"answer":true}`))
	f.Add([]byte(`{"answer":null}`))
	f.Add([]byte(`{"answer":[1,2,3]}`))
	f.Add([]byte(`{"value":"no answer"}`))
	f.Add([]byte(`not json at all`))
	f.Add([]byte(`{}`))
	f.Add([]byte(`[]`))
	f.Add([]byte(`""`))
	f.Add([]byte{0x00, 0x01, 0xff})
	f.Add([]byte(`{"answer":{"nested":"obj"}}`))

	f.Fuzz(func(t *testing.T, data []byte) {
		// Parse as if it were a JSONL answer line — must never panic.
		defer func() {
			if r := recover(); r != nil {
				t.Fatalf("panic on input %q: %v", data, r)
			}
		}()

		var resp map[string]any
		if err := json.Unmarshal(data, &resp); err != nil {
			// Not valid JSON — AgentReceive would return ErrInvalidJSON.
			return
		}

		// Extract "answer" key just like AgentReceive does.
		answer, ok := resp["answer"]
		if !ok {
			// Missing "answer" key — error path, no panic expected.
			return
		}

		// Run through toString (used by most prompt types).
		_ = toString(answer)

		// Run through toBool (used by confirm).
		_ = toBool(answer)
	})
}

// ────────────────────────────────────────────────────────────────────────────
// Prompt base field assertions — common checks for kind, type, message, step
// ────────────────────────────────────────────────────────────────────────────

func TestContractAllPromptsHaveStepAndTotal(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"v"}`+"\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Q?"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines")
	}

	p := lines[1]
	if p["kind"] != "prompt" {
		t.Fatalf("expected kind='prompt', got %v", p["kind"])
	}
	step, ok := p["step"].(float64)
	if !ok || step < 1 {
		t.Fatalf("expected step >= 1, got %v", p["step"])
	}
	// total must be present (value can be null)
	if _, ok := p["total"]; !ok {
		t.Fatal("prompt must have 'total' field")
	}
}

// ────────────────────────────────────────────────────────────────────────────
// helpers
// ────────────────────────────────────────────────────────────────────────────

func assertPromptBase(t *testing.T, p map[string]any, expectedType, expectedMessage string) {
	t.Helper()
	if p["kind"] != "prompt" {
		t.Fatalf("expected kind='prompt', got %v", p["kind"])
	}
	if p["type"] != expectedType {
		t.Fatalf("expected type=%q, got %v", expectedType, p["type"])
	}
	if p["message"] != expectedMessage {
		t.Fatalf("expected message=%q, got %v", expectedMessage, p["message"])
	}
	step, ok := p["step"].(float64)
	if !ok || step < 1 {
		t.Fatalf("expected step >= 1, got %v", p["step"])
	}
	if _, ok := p["total"]; !ok {
		t.Fatal("prompt must have 'total' field")
	}
}
