package prompt

import (
	"bytes"
	"encoding/json"
	"io"
	"os"
	"strings"
	"sync"
	"testing"
)

func agentSetup(t *testing.T, input string) (*os.File, *os.File, func()) {
	t.Helper()
	t.Setenv("INQUIRER_AI_MODE", "agent")

	handshakeOnce = sync.Once{}
	scannerOnce = sync.Once{}
	stdinScanner = nil

	oldStdin := os.Stdin
	oldStdout := os.Stdout

	stdinR, stdinW, _ := os.Pipe()
	stdoutR, stdoutW, _ := os.Pipe()

	os.Stdin = stdinR
	os.Stdout = stdoutW

	go func() {
		stdinW.WriteString(input)
		stdinW.Close()
	}()

	return stdoutR, stdoutW, func() {
		os.Stdin = oldStdin
		os.Stdout = oldStdout
		stdinR.Close()
		stdoutW.Close()
	}
}

func readOutput(r *os.File, w *os.File) []map[string]any {
	w.Close()
	var buf bytes.Buffer
	io.Copy(&buf, r)
	r.Close()

	var results []map[string]any
	for _, line := range strings.Split(strings.TrimSpace(buf.String()), "\n") {
		if line == "" {
			continue
		}
		var m map[string]any
		json.Unmarshal([]byte(line), &m)
		results = append(results, m)
	}
	return results
}

func TestTextAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"hello"}`+"\n")
	defer cleanup()

	result, err := Text(TextConfig{Message: "Name?"})
	lines := readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "hello" {
		t.Fatalf("expected 'hello', got %q", result)
	}
	if lines[0]["protocol"] != "inquirer-ai" {
		t.Fatal("missing handshake")
	}
	if lines[1]["type"] != "input" {
		t.Fatalf("expected type 'input', got %v", lines[1]["type"])
	}
}

func TestTextAgentDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	result, err := Text(TextConfig{Message: "Name?", Default: "World"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "World" {
		t.Fatalf("expected 'World', got %q", result)
	}
}

func TestConfirmAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":true}`+"\n")
	defer cleanup()

	result, err := Confirm(ConfirmConfig{Message: "Continue?"})
	lines := readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result {
		t.Fatal("expected true")
	}
	if lines[1]["type"] != "confirm" {
		t.Fatalf("expected type 'confirm', got %v", lines[1]["type"])
	}
}

func TestSelectAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"b"}`+"\n")
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
	if result != "b" {
		t.Fatalf("expected 'b', got %v", result)
	}
}

func TestSelectAgentInvalid(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"nope"}`+"\n")
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "A", Value: "a"},
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for invalid choice")
	}
}

func TestCheckboxAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a","c"]}`+"\n")
	defer cleanup()

	result, err := Checkbox(CheckboxConfig{
		Message: "Pick",
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
}

func TestPasswordAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"s3cret"}`+"\n")
	defer cleanup()

	result, err := Password(PasswordConfig{Message: "Token?"})
	lines := readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "s3cret" {
		t.Fatalf("expected 's3cret', got %q", result)
	}
	if lines[1]["type"] != "password" {
		t.Fatalf("expected type 'password', got %v", lines[1]["type"])
	}
}

func TestNumberAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":42}`+"\n")
	defer cleanup()

	result, err := Number(NumberConfig{Message: "Port?"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != 42 {
		t.Fatalf("expected 42, got %v", result)
	}
}

func TestExpandAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"y"}`+"\n")
	defer cleanup()

	result, err := Expand(ExpandConfig{
		Message: "Action?",
		Choices: []ExpandChoice{
			{Key: "y", Name: "Yes", Value: "yes"},
			{Key: "n", Name: "No", Value: "no"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "yes" {
		t.Fatalf("expected 'yes', got %v", result)
	}
}

func TestRawlistAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":2}`+"\n")
	defer cleanup()

	result, err := Rawlist(RawlistConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Choice{Name: "First", Value: "1st"},
			Choice{Name: "Second", Value: "2nd"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "2nd" {
		t.Fatalf("expected '2nd', got %v", result)
	}
}

func TestEditorAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"edited text"}`+"\n")
	defer cleanup()

	result, err := Editor(EditorConfig{Message: "Edit"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "edited text" {
		t.Fatalf("expected 'edited text', got %q", result)
	}
}

func TestEmptyStdinRaises(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Name?"})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for empty stdin")
	}
}

func TestInvalidJSON(t *testing.T) {
	r, w, cleanup := agentSetup(t, "not json\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Name?"})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
}

func TestMissingAnswerKey(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"value":"hello"}`+"\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Name?"})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected error for missing answer key")
	}
}

func TestSeparatorAndDisabled(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"ok"}`+"\n")
	defer cleanup()

	result, err := Select(SelectConfig{
		Message: "Pick",
		Choices: []ChoiceItem{
			Separator{Text: "---"},
			Choice{Name: "Disabled", Value: "d", Disabled: true},
			Choice{Name: "OK", Value: "ok"},
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "ok" {
		t.Fatalf("expected 'ok', got %v", result)
	}
}

func TestHandshakeSentOnce(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"a"}`+"\n"+`{"answer":"b"}`+"\n")
	defer cleanup()

	Text(TextConfig{Message: "Q1"})
	Text(TextConfig{Message: "Q2"})
	lines := readOutput(r, w)

	handshakeCount := 0
	for _, l := range lines {
		if l["protocol"] == "inquirer-ai" {
			handshakeCount++
		}
	}
	if handshakeCount != 1 {
		t.Fatalf("expected 1 handshake, got %d", handshakeCount)
	}
}

func TestPathAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"/tmp/test"}`+"\n")
	defer cleanup()

	result, err := Path(PathConfig{Message: "Path?"})
	lines := readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "/tmp/test" {
		t.Fatalf("expected '/tmp/test', got %q", result)
	}
	if lines[1]["type"] != "path" {
		t.Fatalf("expected type 'path', got %v", lines[1]["type"])
	}
}

func TestPathAgentDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	result, err := Path(PathConfig{Message: "Path?", Default: "/home"})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "/home" {
		t.Fatalf("expected '/home', got %q", result)
	}
}

func TestAutocompleteAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"golang"}`+"\n")
	defer cleanup()

	result, err := Autocomplete(AutocompleteConfig{
		Message: "Lang?",
		Choices: []string{"python", "golang", "rust"},
	})
	lines := readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "golang" {
		t.Fatalf("expected 'golang', got %q", result)
	}
	if lines[1]["type"] != "autocomplete" {
		t.Fatalf("expected type 'autocomplete', got %v", lines[1]["type"])
	}
}

func TestAutocompleteAcceptsNonChoice(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"java"}`+"\n")
	defer cleanup()

	result, err := Autocomplete(AutocompleteConfig{
		Message: "Lang?",
		Choices: []string{"python", "golang"},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "java" {
		t.Fatalf("expected 'java', got %q", result)
	}
}

func TestSearchAgent(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"pg"}`+"\n")
	defer cleanup()

	result, err := Search(SearchConfig{
		Message: "DB?",
		Source: func(term string) []ChoiceItem {
			return []ChoiceItem{
				Choice{Name: "PostgreSQL", Value: "pg"},
				Choice{Name: "MySQL", Value: "mysql"},
			}
		},
	})
	lines := readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "pg" {
		t.Fatalf("expected 'pg', got %v", result)
	}
	if lines[1]["type"] != "search" {
		t.Fatalf("expected type 'search', got %v", lines[1]["type"])
	}
}

func TestSearchNilSourceError(t *testing.T) {
	_, err := Search(SearchConfig{Message: "Q"})
	if err == nil {
		t.Fatal("expected error for nil source")
	}
}
