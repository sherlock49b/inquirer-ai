package prompt

import (
	"fmt"
	"strings"
	"sync"
	"testing"
)

// ── Helpers ──

// callLog tracks the order of callback invocations.
type callLog struct {
	mu    sync.Mutex
	calls []string
}

func (c *callLog) record(name string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.calls = append(c.calls, name)
}

func (c *callLog) get() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	cp := make([]string, len(c.calls))
	copy(cp, c.calls)
	return cp
}

// ── Test 1: Order invariant — validate is called before filter ──

func TestTextCallbackOrder_ValidateBeforeFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"hello"}`+"\n")
	defer cleanup()

	log := &callLog{}
	_, err := Text(TextConfig{
		Message: "Q",
		Validate: func(s string) error {
			log.record("validate")
			return nil
		},
		Filter: func(s string) string {
			log.record("filter")
			return s
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	calls := log.get()
	if len(calls) != 2 {
		t.Fatalf("expected 2 calls, got %d: %v", len(calls), calls)
	}
	if calls[0] != "validate" || calls[1] != "filter" {
		t.Fatalf("expected [validate, filter], got %v", calls)
	}
}

func TestSelectCallbackOrder_ValidateBeforeFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"a"}`+"\n")
	defer cleanup()

	log := &callLog{}
	_, err := Select(SelectConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Validate: func(v any) error {
			log.record("validate")
			return nil
		},
		Filter: func(v any) any {
			log.record("filter")
			return v
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	calls := log.get()
	if len(calls) != 2 {
		t.Fatalf("expected 2 calls, got %d: %v", len(calls), calls)
	}
	if calls[0] != "validate" || calls[1] != "filter" {
		t.Fatalf("expected [validate, filter], got %v", calls)
	}
}

func TestCheckboxCallbackOrder_ValidateBeforeFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a"]}`+"\n")
	defer cleanup()

	log := &callLog{}
	_, err := Checkbox(CheckboxConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Validate: func(v any) error {
			log.record("validate")
			return nil
		},
		Filter: func(v any) any {
			log.record("filter")
			return v
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	calls := log.get()
	if len(calls) != 2 {
		t.Fatalf("expected 2 calls, got %d: %v", len(calls), calls)
	}
	if calls[0] != "validate" || calls[1] != "filter" {
		t.Fatalf("expected [validate, filter], got %v", calls)
	}
}

func TestExpandCallbackOrder_ValidateBeforeFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"y"}`+"\n")
	defer cleanup()

	log := &callLog{}
	_, err := Expand(ExpandConfig{
		Message: "Q",
		Choices: []ExpandChoice{{Key: "y", Name: "Yes", Value: "yes"}},
		Validate: func(v any) error {
			log.record("validate")
			return nil
		},
		Filter: func(v any) any {
			log.record("filter")
			return v
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	calls := log.get()
	if len(calls) != 2 {
		t.Fatalf("expected 2 calls, got %d: %v", len(calls), calls)
	}
	if calls[0] != "validate" || calls[1] != "filter" {
		t.Fatalf("expected [validate, filter], got %v", calls)
	}
}

// ── Test 2: Filter NOT called when validate rejects ──

func TestTextFilterNotCalledOnRejection(t *testing.T) {
	// 3 rejections => exhausts retries
	input := strings.Repeat(`{"answer":"bad"}`+"\n", 3)
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	filterCalled := false
	_, err := Text(TextConfig{
		Message: "Q",
		Validate: func(s string) error {
			return fmt.Errorf("rejected")
		},
		Filter: func(s string) string {
			filterCalled = true
			return s
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
	if filterCalled {
		t.Fatal("filter should NOT be called when validate rejects")
	}
}

func TestSelectFilterNotCalledOnRejection(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"a"}`+"\n")
	defer cleanup()

	filterCalled := false
	_, err := Select(SelectConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Validate: func(v any) error {
			return fmt.Errorf("rejected")
		},
		Filter: func(v any) any {
			filterCalled = true
			return v
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
	if filterCalled {
		t.Fatal("filter should NOT be called when validate rejects")
	}
}

func TestCheckboxFilterNotCalledOnRejection(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":["a"]}`+"\n")
	defer cleanup()

	filterCalled := false
	_, err := Checkbox(CheckboxConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Validate: func(v any) error {
			return fmt.Errorf("rejected")
		},
		Filter: func(v any) any {
			filterCalled = true
			return v
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error")
	}
	if filterCalled {
		t.Fatal("filter should NOT be called when validate rejects")
	}
}

// ── Test 3: Filter receives raw (pre-validate) value ──

func TestTextFilterReceivesRawValue(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":"  RAW  "}`+"\n")
	defer cleanup()

	var filterInput string
	result, err := Text(TextConfig{
		Message: "Q",
		Validate: func(s string) error {
			// validate sees raw input
			if !strings.Contains(s, "RAW") {
				return fmt.Errorf("expected RAW")
			}
			return nil
		},
		Filter: func(s string) string {
			filterInput = s
			return strings.TrimSpace(s)
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// filter receives the same raw value that validate saw
	if filterInput != "  RAW  " {
		t.Fatalf("filter should receive raw value '  RAW  ', got %q", filterInput)
	}
	// but result is trimmed by filter
	if result != "RAW" {
		t.Fatalf("expected trimmed 'RAW', got %q", result)
	}
}

// ── Test 4: Multiple rejections, filter called only on accepted value ──

func TestTextMultipleRejectionsFilterCalledOnce(t *testing.T) {
	input := `{"answer":"bad1"}` + "\n" +
		`{"answer":"bad2"}` + "\n" +
		`{"answer":"good"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	filterCount := 0
	var filterValue string
	attempt := 0
	_, err := Text(TextConfig{
		Message: "Q",
		Validate: func(s string) error {
			attempt++
			if attempt <= 2 {
				return fmt.Errorf("not yet")
			}
			return nil
		},
		Filter: func(s string) string {
			filterCount++
			filterValue = s
			return s + "_filtered"
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if filterCount != 1 {
		t.Fatalf("filter should be called exactly once, was called %d times", filterCount)
	}
	if filterValue != "good" {
		t.Fatalf("filter should receive 'good', got %q", filterValue)
	}
}

func TestSelectMultipleRejectionsFilterCalledOnce(t *testing.T) {
	// Select only gets one shot per answer in agent mode (invalid choice error),
	// so we provide 3 answers where the first 2 are valid choices but validate rejects.
	input := `{"answer":"a"}` + "\n" +
		`{"answer":"a"}` + "\n" +
		`{"answer":"a"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	filterCount := 0
	attempt := 0
	_, err := Select(SelectConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
		Validate: func(v any) error {
			attempt++
			if attempt <= 2 {
				return fmt.Errorf("not yet")
			}
			return nil
		},
		Filter: func(v any) any {
			filterCount++
			return v
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if filterCount != 1 {
		t.Fatalf("filter should be called exactly once, was called %d times", filterCount)
	}
}

// ── Test 5: Cross-type consistency — same order across Text, Select, Checkbox, Expand ──

func TestCrossTypeCallbackOrderConsistency(t *testing.T) {
	type testCase struct {
		name  string
		input string
		run   func(log *callLog) error
	}
	cases := []testCase{
		{
			name:  "Text",
			input: `{"answer":"hello"}` + "\n",
			run: func(log *callLog) error {
				_, err := Text(TextConfig{
					Message:  "Q",
					Validate: func(s string) error { log.record("validate"); return nil },
					Filter:   func(s string) string { log.record("filter"); return s },
				})
				return err
			},
		},
		{
			name:  "Select",
			input: `{"answer":"a"}` + "\n",
			run: func(log *callLog) error {
				_, err := Select(SelectConfig{
					Message:  "Q",
					Choices:  []ChoiceItem{Choice{Name: "A", Value: "a"}},
					Validate: func(v any) error { log.record("validate"); return nil },
					Filter:   func(v any) any { log.record("filter"); return v },
				})
				return err
			},
		},
		{
			name:  "Checkbox",
			input: `{"answer":["a"]}` + "\n",
			run: func(log *callLog) error {
				_, err := Checkbox(CheckboxConfig{
					Message:  "Q",
					Choices:  []ChoiceItem{Choice{Name: "A", Value: "a"}},
					Validate: func(v any) error { log.record("validate"); return nil },
					Filter:   func(v any) any { log.record("filter"); return v },
				})
				return err
			},
		},
		{
			name:  "Expand",
			input: `{"answer":"y"}` + "\n",
			run: func(log *callLog) error {
				_, err := Expand(ExpandConfig{
					Message:  "Q",
					Choices:  []ExpandChoice{{Key: "y", Name: "Yes", Value: "yes"}},
					Validate: func(v any) error { log.record("validate"); return nil },
					Filter:   func(v any) any { log.record("filter"); return v },
				})
				return err
			},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			r, w, cleanup := agentSetup(t, tc.input)
			defer cleanup()

			log := &callLog{}
			if err := tc.run(log); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			readOutput(r, w)

			calls := log.get()
			if len(calls) != 2 {
				t.Fatalf("expected 2 calls, got %d: %v", len(calls), calls)
			}
			if calls[0] != "validate" || calls[1] != "filter" {
				t.Fatalf("expected [validate, filter], got %v", calls)
			}
		})
	}
}

// ── Number-specific tests ──

func TestNumberCallbackOrder_ValidateBeforeFilter(t *testing.T) {
	r, w, cleanup := agentSetup(t, `{"answer":10}`+"\n")
	defer cleanup()

	log := &callLog{}
	_, err := Number(NumberConfig{
		Message: "Q",
		Validate: func(v float64) error {
			log.record("validate")
			return nil
		},
		Filter: func(v float64) float64 {
			log.record("filter")
			return v
		},
	})
	readOutput(r, w)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	calls := log.get()
	if len(calls) != 2 {
		t.Fatalf("expected 2 calls, got %d: %v", len(calls), calls)
	}
	if calls[0] != "validate" || calls[1] != "filter" {
		t.Fatalf("expected [validate, filter], got %v", calls)
	}
}

func TestNumberFilterNotCalledOnBuiltInRejection(t *testing.T) {
	// Value exceeds max, so built-in validation rejects before filter/validate run
	min := 0.0
	max := 5.0
	r, w, cleanup := agentSetup(t, `{"answer":100}`+"\n")
	defer cleanup()

	filterCalled := false
	validateCalled := false
	_, err := Number(NumberConfig{
		Message: "Q",
		Min:     &min,
		Max:     &max,
		Validate: func(v float64) error {
			validateCalled = true
			return nil
		},
		Filter: func(v float64) float64 {
			filterCalled = true
			return v
		},
	})
	readOutput(r, w)

	if err == nil {
		t.Fatal("expected validation error for out-of-range value")
	}
	if filterCalled {
		t.Fatal("filter should NOT be called when built-in validation rejects")
	}
	if validateCalled {
		t.Fatal("user validate should NOT be called when built-in validation rejects")
	}
}
