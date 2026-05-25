package prompt_test

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// demoBinary is the path to the compiled demo binary, built once per test run.
var demoBinary string

func TestMain(m *testing.M) {
	// Build the demo binary once before all tests.
	tmpDir, err := os.MkdirTemp("", "inquirer-ai-integration-*")
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to create temp dir: %v\n", err)
		os.Exit(1)
	}
	defer os.RemoveAll(tmpDir)

	bin := filepath.Join(tmpDir, "demo")

	// Find the go/ directory (parent of prompt/).
	wd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "getwd: %v\n", err)
		os.Exit(1)
	}
	goDir := filepath.Dir(wd)

	cmd := exec.Command("go", "build", "-o", bin, "./examples/demo/")
	cmd.Dir = goDir
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	out, err := cmd.CombinedOutput()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to build demo binary: %v\n%s\n", err, out)
		os.Exit(1)
	}
	demoBinary = bin

	os.Exit(m.Run())
}

func buildDemo(t *testing.T) string {
	t.Helper()
	if demoBinary == "" {
		t.Fatal("demo binary not built; TestMain should have built it")
	}
	return demoBinary
}

// runDemo executes the demo binary with the given JSON answers piped to stdin.
// Returns stdout lines as parsed JSON maps, stderr string, and exit code.
func runDemo(t *testing.T, answers []map[string]any) (lines []map[string]any, stderr string, exitCode int) {
	t.Helper()
	bin := buildDemo(t)

	var stdinBuf bytes.Buffer
	for _, a := range answers {
		data, err := json.Marshal(a)
		if err != nil {
			t.Fatalf("marshal answer: %v", err)
		}
		stdinBuf.Write(data)
		stdinBuf.WriteByte('\n')
	}

	cmd := exec.Command(bin)
	cmd.Stdin = &stdinBuf
	cmd.Env = []string{"INQUIRER_AI_MODE=agent", "INQUIRER_AI_TRANSPORT=stdio"}

	var stdoutBuf, stderrBuf bytes.Buffer
	cmd.Stdout = &stdoutBuf
	cmd.Stderr = &stderrBuf

	err := cmd.Run()
	exitCode = 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			t.Fatalf("exec error: %v", err)
		}
	}

	// Parse JSON objects from stdout. The demo prints a text banner
	// before JSON, so we skip non-JSON prefix lines and use a streaming
	// decoder from the first '{' onward. This handles both single-line
	// JSONL and the multi-line json.MarshalIndent output at the end.
	raw := stdoutBuf.String()
	jsonStart := strings.Index(raw, "{")
	if jsonStart < 0 {
		return lines, stderrBuf.String(), exitCode
	}
	dec := json.NewDecoder(strings.NewReader(raw[jsonStart:]))
	for dec.More() {
		var m map[string]any
		if err := dec.Decode(&m); err != nil {
			break
		}
		lines = append(lines, m)
	}
	return lines, stderrBuf.String(), exitCode
}

func TestIntegrationHandshakeFirst(t *testing.T) {
	// Send all correct answers so the binary runs to completion;
	// we only care about the first JSON line here.
	answers := happyPathAnswers()
	lines, _, exitCode := runDemo(t, answers)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d", exitCode)
	}
	if len(lines) == 0 {
		t.Fatal("no JSON output lines")
	}
	hs := lines[0]
	if hs["protocol"] != "inquirer-ai" {
		t.Fatalf("first line should be handshake, got %v", hs)
	}
	if hs["version"] != "0.2.1" {
		t.Fatalf("expected version 0.2.1, got %v", hs["version"])
	}
	if hs["format"] != "jsonl" {
		t.Fatalf("expected format jsonl, got %v", hs["format"])
	}
}

func TestIntegrationHappyPath(t *testing.T) {
	answers := happyPathAnswers()
	lines, _, exitCode := runDemo(t, answers)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d", exitCode)
	}

	// Last JSON line should be the final config output from the demo.
	if len(lines) == 0 {
		t.Fatal("no JSON output")
	}
	final := lines[len(lines)-1]

	// Verify the fields written by the demo's json.MarshalIndent.
	if final["project"] != "my-project" {
		t.Fatalf("expected project='my-project', got %v", final["project"])
	}
	if final["template"] != "web-api" {
		t.Fatalf("expected template='web-api', got %v", final["template"])
	}
	if final["license"] != "MIT" {
		t.Fatalf("expected license='MIT', got %v", final["license"])
	}

	// features is []any in JSON
	features, ok := final["features"].([]any)
	if !ok {
		t.Fatalf("expected features to be a list, got %T", final["features"])
	}
	if len(features) != 2 {
		t.Fatalf("expected 2 features, got %d", len(features))
	}
	if features[0] != "docker" || features[1] != "ci" {
		t.Fatalf("unexpected features: %v", features)
	}

	// port is a float64 in JSON
	port, ok := final["port"].(float64)
	if !ok {
		t.Fatalf("expected port to be a number, got %T", final["port"])
	}
	if port != 3000 {
		t.Fatalf("expected port=3000, got %v", port)
	}

	// Verify prompt types appeared in order (skip handshake at index 0).
	promptTypes := []string{"input", "select", "select", "checkbox", "confirm", "number"}
	idx := 0
	for _, line := range lines[1:] {
		if tp, ok := line["type"].(string); ok {
			if idx < len(promptTypes) {
				if tp != promptTypes[idx] {
					t.Fatalf("prompt %d: expected type %q, got %q", idx, promptTypes[idx], tp)
				}
				idx++
			}
		}
	}
	if idx != len(promptTypes) {
		t.Fatalf("expected %d prompts, found %d", len(promptTypes), idx)
	}
}

func TestIntegrationEOF(t *testing.T) {
	// Send only one answer then close stdin — the demo should fail.
	answers := []map[string]any{
		{"answer": "my-project"},
	}
	_, stderr, exitCode := runDemo(t, answers)

	if exitCode == 0 {
		t.Fatal("expected non-zero exit code when stdin closes early")
	}
	if !strings.Contains(stderr, "Error") {
		t.Fatalf("expected error message on stderr, got: %q", stderr)
	}
}

func TestIntegrationInvalidChoice(t *testing.T) {
	// First answer is fine, second is an invalid select choice.
	answers := []map[string]any{
		{"answer": "my-project"},
		{"answer": "nonexistent-template"},
	}
	_, stderr, exitCode := runDemo(t, answers)

	if exitCode == 0 {
		t.Fatal("expected non-zero exit code for invalid select choice")
	}
	if !strings.Contains(stderr, "Error") {
		t.Fatalf("expected error on stderr, got: %q", stderr)
	}
}

// happyPathAnswers returns the 6 correct JSON answers for the demo binary.
func happyPathAnswers() []map[string]any {
	return []map[string]any{
		{"answer": "my-project"},             // Text: project name
		{"answer": "web-api"},                // Select: template
		{"answer": "MIT"},                    // Select: license
		{"answer": []string{"docker", "ci"}}, // Checkbox: features
		{"answer": true},                     // Confirm: continue
		{"answer": 3000},                     // Number: port
	}
}
