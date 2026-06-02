package prompt

import (
	"bufio"
	"encoding/json"
	"errors"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// ── R2: numeric-string grammar ──

func TestNumberGrammar_AcceptReject(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}

	accept := map[string]float64{
		"1e3":    1000,
		"  5  ":  5,
		"3.5":    3.5,
		"-2":     -2,
		"1E-3":   0.001,
		"+7":     7,
		"0":      0,
		"42":     42,
		"\t10\n": 10,
		"1.5e2":  150,
	}
	for in, want := range accept {
		got, err := validateNumber(in, cfg)
		if err != nil {
			t.Errorf("validateNumber(%q) unexpected error: %v", in, err)
			continue
		}
		if got != want {
			t.Errorf("validateNumber(%q) = %v, want %v", in, got, want)
		}
	}

	reject := []string{"1_000", "3abc", "0x10", ".5", "5.", "", "+", "-", "e3", "1e", "NaN", "Inf", "Infinity", " ", "1.2.3"}
	for _, in := range reject {
		if _, err := validateNumber(in, cfg); err == nil {
			t.Errorf("validateNumber(%q) should be rejected", in)
		} else if !strings.Contains(err.Error(), "Not a valid number") {
			t.Errorf("validateNumber(%q) error = %q, want to contain %q", in, err.Error(), "Not a valid number")
		}
	}
}

func TestNumberGrammar_IntegralCoercionMessage(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: false}
	_, err := validateNumber("3.5", cfg)
	if err == nil || !strings.Contains(err.Error(), "Decimal numbers are not allowed") {
		t.Fatalf("expected 'Decimal numbers are not allowed', got %v", err)
	}
	// integral float string accepted when floats disallowed
	if _, err := validateNumber("3.0", cfg); err != nil {
		t.Fatalf("integral float string should be accepted: %v", err)
	}
}

func TestNumberGrammar_TypeMessages(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}
	_, err := validateNumber(true, cfg)
	if err == nil || !strings.Contains(err.Error(), "Expected a number") {
		t.Fatalf("bool should yield 'Expected a number', got %v", err)
	}
}

// ── R4: type-aware value matching, disabled "" → enabled ──

func TestAnswerMatchesValue_TypeAware(t *testing.T) {
	// string "42" must NOT match numeric 42
	if answerMatchesValue("42", 42) {
		t.Error(`string "42" must not match number 42`)
	}
	if answerMatchesValue(float64(42), "42") {
		t.Error(`number 42 must not match string "42"`)
	}
	// bool must not match number
	if answerMatchesValue(true, float64(1)) {
		t.Error("bool true must not match number 1")
	}
	if answerMatchesValue(float64(1), true) {
		t.Error("number 1 must not match bool true")
	}
	// numeric equality across int/float representations
	if !answerMatchesValue(float64(1), 1) {
		t.Error("answer 1.0 should match int value 1")
	}
	if !answerMatchesValue("hello", "hello") {
		t.Error("string should match equal string")
	}
	if !answerMatchesValue(true, true) {
		t.Error("bool should match equal bool")
	}
}

func TestIsDisabled_EmptyStringIsEnabled(t *testing.T) {
	cases := []struct {
		val  any
		want bool
	}{
		{nil, false},
		{false, false},
		{"", false},
		{true, true},
		{"coming soon", true},
		{float64(0), false},
	}
	for _, c := range cases {
		if got := isDisabled(c.val); got != c.want {
			t.Errorf("isDisabled(%#v) = %v, want %v", c.val, got, c.want)
		}
	}
	// IsSelectable: choice with disabled:"" is selectable
	if !IsSelectable(Choice{Name: "x", Value: "x", Disabled: ""}) {
		t.Error(`choice with disabled:"" must be selectable`)
	}
	if IsSelectable(Choice{Name: "x", Value: "x", Disabled: "nope"}) {
		t.Error("choice with non-empty disabled string must not be selectable")
	}
}

func TestSelectAgent_TypeAwareMatch(t *testing.T) {
	// numeric answer must match numeric value, not the string value of another choice
	r, w, cleanup := agentSetup(t, `{"answer":1}`+"\n")
	defer cleanup()

	got, err := Select(SelectConfig{
		Message: "pick",
		Choices: []ChoiceItem{
			Choice{Name: "one", Value: float64(1)},
			Choice{Name: "str", Value: "1"},
		},
	})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != float64(1) {
		t.Fatalf("expected numeric value 1, got %#v", got)
	}
}

func TestSelectAgent_StringDoesNotMatchNumericValue(t *testing.T) {
	// Provide 3 identical invalid answers so the unified retry budget is
	// exhausted and we get the choice error (not an EOF abort).
	line := `{"answer":"1"}` + "\n"
	r, w, cleanup := agentSetup(t, line+line+line)
	defer cleanup()

	got, err := Select(SelectConfig{
		Message: "pick",
		Choices: []ChoiceItem{
			Choice{Name: "one", Value: float64(1)},
		},
	})
	_ = readOutput(r, w)
	// "1" does not match value 1 (number) and does not match name "one" → invalid choice
	if err == nil {
		t.Fatalf(`string "1" must not match numeric value 1, got %#v`, got)
	}
	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got %v", err)
	}
}

// ── R5: confirm/password null → default; text/path/autocomplete empty verbatim ──

func TestConfirmAgent_NullUsesDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	got, err := Confirm(ConfirmConfig{Message: "ok?", Default: true})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != true {
		t.Fatalf("null answer should resolve to default true, got %v", got)
	}
}

func TestPasswordAgent_NullUsesDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	got, err := Password(PasswordConfig{Message: "pw", Default: "s3cret"})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "s3cret" {
		t.Fatalf("null answer should resolve to default, got %q", got)
	}
}

func TestTextAgent_EmptyStringVerbatim(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":""}`+"\n")
	defer cleanup()

	got, err := Text(TextConfig{Message: "name", Default: "fallback"})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "" {
		t.Fatalf(`explicit "" must be returned verbatim, got %q`, got)
	}
}

func TestTextAgent_NullUsesDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":null}`+"\n")
	defer cleanup()

	got, err := Text(TextConfig{Message: "name", Default: "fallback"})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "fallback" {
		t.Fatalf("null must resolve to default, got %q", got)
	}
}

func TestPathAgent_EmptyStringVerbatimAndNoNormalize(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"./a/../b/"}`+"\n")
	defer cleanup()

	got, err := Path(PathConfig{Message: "p", Default: "/home", OnlyDirectories: true})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "./a/../b/" {
		t.Fatalf("path must be returned verbatim (no Clean), got %q", got)
	}
}

func TestAutocompleteAgent_EmptyStringVerbatim(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":""}`+"\n")
	defer cleanup()

	got, err := Autocomplete(AutocompleteConfig{Message: "x", Default: "dft"})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "" {
		t.Fatalf(`explicit "" must be verbatim, got %q`, got)
	}
}

// ── R5: rawlist integer index ──

func TestRawlistAgent_RejectsNonIntegerIndex(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":1.5}`+"\n")
	defer cleanup()

	_, err := Rawlist(RawlistConfig{
		Message: "pick",
		Choices: []ChoiceItem{
			Choice{Name: "a", Value: "a"},
			Choice{Name: "b", Value: "b"},
		},
	})
	_ = readOutput(r, w)
	if err == nil {
		t.Fatal("non-integer index 1.5 must be rejected (not truncated)")
	}
}

func TestRawlistAgent_IntegerIndexSelectableOnly(t *testing.T) {
	// index 2 should select the 2nd SELECTABLE item, skipping a separator/disabled.
	r, w, cleanup := agentSetup(t, `{"answer":2}`+"\n")
	defer cleanup()

	got, err := Rawlist(RawlistConfig{
		Message: "pick",
		Choices: []ChoiceItem{
			Choice{Name: "a", Value: "a"},
			Separator{Text: "--"},
			Choice{Name: "b", Value: "b", Disabled: true},
			Choice{Name: "c", Value: "c"},
		},
	})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "c" {
		t.Fatalf("index 2 over selectable list should pick 'c', got %#v", got)
	}
}

func TestRawlistPayload_SelectableOnlyAndDefault(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":1}`+"\n")
	defer cleanup()

	_, err := Rawlist(RawlistConfig{
		Message: "pick",
		Choices: []ChoiceItem{
			Choice{Name: "a", Value: "a"},
			Separator{Text: "--"},
			Choice{Name: "b", Value: "b", Disabled: true},
			Choice{Name: "c", Value: "c"},
		},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	lines := readOutput(r, w)
	p := lines[len(lines)-1]
	if _, ok := p["default"]; !ok {
		t.Fatal("rawlist payload must include 'default'")
	}
	choices := p["choices"].([]any)
	if len(choices) != 2 {
		t.Fatalf("rawlist payload must exclude separators and disabled (want 2 selectable), got %d", len(choices))
	}
}

// ── R5: search resolution + verbatim fallback ──

func TestSearchAgent_ResolveMatchToValue(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"PostgreSQL"}`+"\n")
	defer cleanup()

	got, err := Search(SearchConfig{
		Message: "db",
		Source: func(string) []ChoiceItem {
			return []ChoiceItem{Choice{Name: "PostgreSQL", Value: "pg"}}
		},
	})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "pg" {
		t.Fatalf("name match must resolve to value 'pg', got %#v", got)
	}
}

func TestSearchAgent_VerbatimFallback(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"custom-thing"}`+"\n")
	defer cleanup()

	got, err := Search(SearchConfig{
		Message: "db",
		Source: func(string) []ChoiceItem {
			return []ChoiceItem{Choice{Name: "PostgreSQL", Value: "pg"}}
		},
	})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "custom-thing" {
		t.Fatalf("non-match must return verbatim string, got %#v", got)
	}
}

// ── R3: mode detection (INQUIRER_AI_SOCKET activates agent mode even on TTY) ──

func TestMode_SocketEnvActivatesAgent(t *testing.T) {
	t.Setenv("INQUIRER_AI_MODE", "")
	t.Setenv("INQUIRER_AI_SOCKET", "/tmp/whatever.sock")
	if !IsAgentMode() {
		t.Fatal("INQUIRER_AI_SOCKET set must activate agent mode")
	}
	if !socketRequested() {
		t.Fatal("INQUIRER_AI_SOCKET set must request socket transport")
	}
}

func TestMode_HumanOverridesSocket(t *testing.T) {
	t.Setenv("INQUIRER_AI_MODE", "HUMAN")
	t.Setenv("INQUIRER_AI_SOCKET", "/tmp/whatever.sock")
	if IsAgentMode() {
		t.Fatal("MODE=human must force terminal mode even with SOCKET set")
	}
}

func TestMode_AgentRequestsSocket(t *testing.T) {
	t.Setenv("INQUIRER_AI_MODE", "AGENT")
	t.Setenv("INQUIRER_AI_SOCKET", "")
	if !socketRequested() {
		t.Fatal("MODE=agent must request socket transport")
	}
}

// ── R10: socket hardening ──

func TestSocket_RefusesNonSocketFile(t *testing.T) {
	dir := t.TempDir()
	regular := filepath.Join(dir, "notasocket.sock")
	if err := os.WriteFile(regular, []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := newSocketTransport(regular)
	if err == nil {
		t.Fatal("must refuse to use a path that is an existing non-socket file")
	}
	if !strings.Contains(err.Error(), "not a socket") {
		t.Fatalf("expected 'not a socket' error, got %v", err)
	}
	// the regular file must NOT have been removed
	if _, statErr := os.Stat(regular); statErr != nil {
		t.Fatal("must never unlink a non-socket file")
	}
}

func TestSocket_RemovesStaleSocket(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "stale.sock")
	// Create a real stale socket and close its listener (leaving the file).
	l, err := net.Listen("unix", p)
	if err != nil {
		t.Fatal(err)
	}
	l.Close()
	// File still exists; new transport should reclaim it.
	st, err := newSocketTransport(p)
	if err != nil {
		t.Fatalf("should reclaim a stale socket file, got %v", err)
	}
	st.Cleanup()
}

func TestSocket_EnvPathValidation(t *testing.T) {
	// relative path rejected
	if _, err := newSocketTransport("relative.sock"); err == nil {
		t.Fatal("relative INQUIRER_AI_SOCKET must be rejected")
	}
	// nonexistent parent rejected
	if _, err := newSocketTransport("/no/such/dir/here/x.sock"); err == nil {
		t.Fatal("nonexistent parent dir must be rejected")
	}
	// too-long path rejected
	long := "/tmp/" + strings.Repeat("a", 110) + ".sock"
	if _, err := newSocketTransport(long); err == nil {
		t.Fatal("over-long socket path must be rejected")
	}
}

func TestSocket_ChmodTo0600(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "perm.sock")
	st, err := newSocketTransport(p)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Cleanup()
	info, err := os.Stat(p)
	if err != nil {
		t.Fatal(err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Fatalf("socket perms = %o, want 600", perm)
	}
}

func TestSocket_CleanupIsIdempotentAndStopsSignals(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "idem.sock")
	st, err := newSocketTransport(p)
	if err != nil {
		t.Fatal(err)
	}
	st.Cleanup()
	// second call must not panic (channel already closed/niled)
	st.Cleanup()
	if _, statErr := os.Stat(p); !os.IsNotExist(statErr) {
		t.Fatal("Cleanup must remove the socket file")
	}
}

// ── R10: PromptCycle must not mutate caller payload ──

func TestPromptCycle_DoesNotMutateCallerPayload(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "nomutate.sock")
	st, err := newSocketTransport(p)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Cleanup()

	payload := map[string]any{"type": "input", "message": "x"}

	done := make(chan struct{})
	go func() {
		defer close(done)
		conn, derr := net.Dial("unix", p)
		if derr != nil {
			return
		}
		defer conn.Close()
		reader := bufio.NewReader(conn)
		// drain JSON lines until prompt, then answer
		for {
			line, rerr := reader.ReadString('\n')
			if rerr != nil {
				return
			}
			var msg map[string]any
			if json.Unmarshal([]byte(strings.TrimSpace(line)), &msg) == nil {
				if kind, _ := msg["kind"].(string); kind == "prompt" {
					break
				}
			}
		}
		_, _ = conn.Write([]byte(`{"answer":"ok"}` + "\n"))
		_, _ = reader.ReadString('\n')
	}()

	_, err = st.PromptCycle(payload, func(a any) (any, error) { return a, nil })
	<-done
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if _, ok := payload["step"]; ok {
		t.Fatal("PromptCycle must not inject 'step' into the caller's payload")
	}
	if _, ok := payload["kind"]; ok {
		t.Fatal("PromptCycle must not inject 'kind' into the caller's payload")
	}
}

// ── R11: confirm validate runs before filter ──

func TestConfirmAgent_ValidateBeforeFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":true}`+"\n")
	defer cleanup()

	var order []string
	got, err := Confirm(ConfirmConfig{
		Message: "ok?",
		Validate: func(v any) error {
			order = append(order, "validate")
			return nil
		},
		Filter: func(v any) any {
			order = append(order, "filter")
			return v
		},
	})
	_ = readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != true {
		t.Fatalf("expected true, got %v", got)
	}
	if len(order) != 2 || order[0] != "validate" || order[1] != "filter" {
		t.Fatalf("expected validate before filter, got %v", order)
	}
}

func TestConfirmAgent_ValidateSeesCoercedValueNotFiltered(t *testing.T) {
	// Validate must receive the coerced bool, and filter must not run when
	// validate fails on the final attempt.
	r, w, cleanup := agentSetup(t, `{"answer":true}`+"\n"+`{"answer":true}`+"\n"+`{"answer":true}`+"\n")
	defer cleanup()

	filterCalled := false
	_, err := Confirm(ConfirmConfig{
		Message:  "ok?",
		Validate: func(v any) error { return errors.New("nope") },
		Filter:   func(v any) any { filterCalled = true; return v },
	})
	_ = readOutput(r, w)
	if err == nil {
		t.Fatal("expected validation failure")
	}
	if filterCalled {
		t.Fatal("filter must not run when validate rejects")
	}
}

// ── go-prompts-7: checkbox uncheck removes the map key ──

func TestCheckboxModel_UncheckDeletesKey(t *testing.T) {
	m := makeCheckboxModel([]string{"a", "b"}, true)
	// toggle on
	updated, _ := m.Update(keyMsg(" "))
	m = updated.(checkboxModel)
	if len(m.checked) != 1 {
		t.Fatalf("after check, len=%d want 1", len(m.checked))
	}
	// toggle off → key deleted, len back to 0
	updated, _ = m.Update(keyMsg(" "))
	m = updated.(checkboxModel)
	if len(m.checked) != 0 {
		t.Fatalf("after uncheck, len=%d want 0 (key must be deleted)", len(m.checked))
	}
}

// ── R1: single 3-attempt retry budget (stdio) ──

func TestAgentStdio_RetryBudgetIsThree(t *testing.T) {
	// three failing answers: 2 validation_error then 1 fatal error.
	input := `{"answer":"x"}` + "\n" + `{"answer":"x"}` + "\n" + `{"answer":"x"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Text(TextConfig{
		Message:  "q",
		Validate: func(string) error { return errors.New("bad") },
	})
	lines := readOutput(r, w)
	if err == nil {
		t.Fatal("expected fatal error after 3 attempts")
	}

	validationErrors, fatalErrors, prompts := 0, 0, 0
	var promptSteps []float64
	for _, l := range lines {
		switch l["kind"] {
		case "validation_error":
			validationErrors++
		case "error":
			fatalErrors++
		case "prompt":
			prompts++
			if s, ok := l["step"].(float64); ok {
				promptSteps = append(promptSteps, s)
			}
		}
	}
	if validationErrors != 2 {
		t.Fatalf("expected exactly 2 validation_error lines, got %d", validationErrors)
	}
	if fatalErrors != 1 {
		t.Fatalf("expected exactly 1 fatal error line, got %d", fatalErrors)
	}
	if prompts != 3 {
		t.Fatalf("expected exactly 3 prompt lines (3 attempts), got %d", prompts)
	}
	// FIX A: "step" is the LOGICAL prompt index. All re-sends of the same
	// logical prompt (the two retries here) must reuse the same step value.
	for i, s := range promptSteps {
		if s != promptSteps[0] {
			t.Fatalf("re-sent prompt %d has step=%v, want %v (re-sends must reuse step)", i, s, promptSteps[0])
		}
	}
}

// ── go-core-3: blank line / EOF → fatal abort, not retry ──

func TestAgentStdio_BlankLineAborts(t *testing.T) {
	r, w, cleanup := agentSetup(t, "\n")
	defer cleanup()

	_, err := Text(TextConfig{Message: "q"})
	_ = readOutput(r, w)
	if err == nil || !errors.Is(err, ErrAborted) {
		t.Fatalf("blank line must be a fatal abort (ErrAborted), got %v", err)
	}
}

func TestAgentStdio_EOFAborts(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()

	_, err := Text(TextConfig{Message: "q"})
	_ = readOutput(r, w)
	if err == nil || !errors.Is(err, ErrAborted) {
		t.Fatalf("EOF must be a fatal abort (ErrAborted), got %v", err)
	}
}

// ── go-socket-4 / R7: canonical socket error messages ──

// socketSendBadLine creates a transport at path, connects a client, drains
// JSON lines until the "prompt" arrives, sends badLine, and returns the next
// JSON message from the transport.
func socketSendBadLine(t *testing.T, path, badLine string) map[string]any {
	t.Helper()
	st, err := newSocketTransport(path)
	if err != nil {
		t.Fatal(err)
	}
	defer st.Cleanup()

	respCh := make(chan map[string]any, 1)
	go func() {
		conn, derr := net.Dial("unix", path)
		if derr != nil {
			respCh <- nil
			return
		}
		defer conn.Close()
		reader := bufio.NewReader(conn)
		for {
			line, rerr := reader.ReadString('\n')
			if rerr != nil {
				respCh <- nil
				return
			}
			var msg map[string]any
			if json.Unmarshal([]byte(strings.TrimSpace(line)), &msg) == nil {
				if kind, _ := msg["kind"].(string); kind == "prompt" {
					break
				}
			}
		}
		if _, werr := conn.Write([]byte(badLine + "\n")); werr != nil {
			respCh <- nil
			return
		}
		line, rerr := reader.ReadString('\n')
		if rerr != nil {
			respCh <- nil
			return
		}
		var resp map[string]any
		_ = json.Unmarshal([]byte(strings.TrimSpace(line)), &resp)
		respCh <- resp
	}()

	go func() {
		_, _ = st.PromptCycle(
			map[string]any{"type": "input", "message": "x"},
			func(a any) (any, error) { return a, nil })
	}()

	return <-respCh
}

func TestSocket_InvalidJSONMessage(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "r7.sock")
	resp := socketSendBadLine(t, p, "not json")
	if resp == nil {
		t.Fatal("no response received")
	}
	msg, _ := resp["message"].(string)
	if !strings.Contains(msg, "Invalid JSON response") {
		t.Fatalf("expected 'Invalid JSON response' message, got %#v", resp)
	}
}

func TestSocket_MissingAnswerMessage(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "r7b.sock")
	resp := socketSendBadLine(t, p, `{"notanswer":1}`)
	if resp == nil {
		t.Fatal("no response received")
	}
	msg, _ := resp["message"].(string)
	if !strings.Contains(msg, `Answer must be a JSON object with an "answer" field`) {
		t.Fatalf("expected canonical missing-answer message, got %#v", resp)
	}
}
