package prompt

import (
	"errors"
	"fmt"
	"testing"
)

func TestErrorHierarchy(t *testing.T) {
	tests := []struct {
		name   string
		err    error
		parent error
	}{
		{"ErrAborted is ErrPrompt", ErrAborted, ErrPrompt},
		{"ErrValidation is ErrPrompt", ErrValidation, ErrPrompt},
		{"ErrInvalidChoice is ErrValidation", ErrInvalidChoice, ErrValidation},
		{"ErrInvalidChoice is ErrPrompt", ErrInvalidChoice, ErrPrompt},
		{"ErrInvalidJSON is ErrPrompt", ErrInvalidJSON, ErrPrompt},
		{"ErrEditor is ErrPrompt", ErrEditor, ErrPrompt},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if !errors.Is(tc.err, tc.parent) {
				t.Fatalf("%v should match %v via errors.Is", tc.err, tc.parent)
			}
		})
	}
}

func TestErrorHierarchyNegative(t *testing.T) {
	if errors.Is(ErrAborted, ErrValidation) {
		t.Fatal("ErrAborted should not match ErrValidation")
	}
	if errors.Is(ErrEditor, ErrValidation) {
		t.Fatal("ErrEditor should not match ErrValidation")
	}
	if errors.Is(ErrInvalidJSON, ErrValidation) {
		t.Fatal("ErrInvalidJSON should not match ErrValidation")
	}
}

func TestWrappedErrorPreservesChain(t *testing.T) {
	wrapped := fmt.Errorf("%w: port out of range", ErrValidation)
	if !errors.Is(wrapped, ErrValidation) {
		t.Fatal("wrapped error should match ErrValidation")
	}
	if !errors.Is(wrapped, ErrPrompt) {
		t.Fatal("wrapped error should match ErrPrompt through chain")
	}
}

func TestInvalidChoiceFromSelectMatchesValidation(t *testing.T) {
	// Provide 3 answers for retry loop.
	input := `{"answer":"nope"}` + "\n" +
		`{"answer":"nope"}` + "\n" +
		`{"answer":"nope"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	_, err := Select(SelectConfig{
		Message: "Q",
		Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}},
	})
	readOutput(r, w)

	if !errors.Is(err, ErrInvalidChoice) {
		t.Fatalf("expected ErrInvalidChoice, got: %v", err)
	}
	if !errors.Is(err, ErrValidation) {
		t.Fatalf("ErrInvalidChoice should also match ErrValidation, got: %v", err)
	}
	if !errors.Is(err, ErrPrompt) {
		t.Fatalf("should match root ErrPrompt, got: %v", err)
	}
}

func TestEOFMatchesAborted(t *testing.T) {
	r, w, cleanup := agentSetup(t, "")
	defer cleanup()

	_, err := Text(TextConfig{Message: "Q"})
	readOutput(r, w)

	if !errors.Is(err, ErrAborted) {
		t.Fatalf("EOF should match ErrAborted, got: %v", err)
	}
	if !errors.Is(err, ErrPrompt) {
		t.Fatalf("should match root ErrPrompt, got: %v", err)
	}
}
