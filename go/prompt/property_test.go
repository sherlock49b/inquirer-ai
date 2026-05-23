package prompt

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"testing"
	"testing/quick"
)

// ── Property: Choice roundtrip (dict → marshal → unmarshal → same values) ──

func TestPropertyChoiceRoundtrip(t *testing.T) {
	f := func(name string, value string) bool {
		if name == "" {
			return true
		}
		c := Choice{Name: name, Value: value}
		items := marshalItems([]ChoiceItem{c})
		data, err := json.Marshal(items[0])
		if err != nil {
			return false
		}
		var parsed map[string]any
		if err := json.Unmarshal(data, &parsed); err != nil {
			return false
		}
		return parsed["name"] == name && parsed["value"] == value
	}
	if err := quick.Check(f, &quick.Config{MaxCount: 500}); err != nil {
		t.Fatal(err)
	}
}

// ── Property: moveCursor always returns a selectable index ──

func TestPropertyMoveCursorAlwaysSelectable(t *testing.T) {
	f := func(numEnabled, numDisabled uint8, direction int8) bool {
		ne := int(numEnabled%10) + 1
		nd := int(numDisabled % 5)

		var items []ChoiceItem
		for i := 0; i < ne; i++ {
			items = append(items, Choice{Name: fmt.Sprintf("e%d", i), Value: fmt.Sprintf("e%d", i)})
		}
		for i := 0; i < nd; i++ {
			items = append(items, Choice{Name: fmt.Sprintf("d%d", i), Value: fmt.Sprintf("d%d", i), Disabled: true})
		}

		choices := parseChoices(items)
		selectable := selectableIndices(choices)
		if len(selectable) == 0 {
			return true
		}

		dir := 1
		if direction < 0 {
			dir = -1
		}
		result := moveCursor(selectable[0], dir, selectable, true)

		for _, idx := range selectable {
			if result == idx {
				return true
			}
		}
		return false
	}
	if err := quick.Check(f, &quick.Config{MaxCount: 1000}); err != nil {
		t.Fatal(err)
	}
}

// ── Property: validateNumber min/max consistency ──

func TestPropertyNumberMinMaxConsistency(t *testing.T) {
	f := func(value float64, lo, hi int8) bool {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return true
		}
		minVal := float64(lo)
		maxVal := float64(hi)
		if minVal > maxVal {
			return true
		}
		cfg := NumberConfig{Min: &minVal, Max: &maxVal, FloatAllowed: true}
		result, err := validateNumber(value, cfg)
		if err != nil {
			return value < minVal || value > maxVal
		}
		return result >= minVal && result <= maxVal
	}
	if err := quick.Check(f, &quick.Config{MaxCount: 1000}); err != nil {
		t.Fatal(err)
	}
}

// ── Property: toBool is deterministic ──

func TestPropertyToBoolDeterministic(t *testing.T) {
	inputs := []any{true, false, "y", "yes", "n", "no", "true", "false", "1", "0", "Y", "YES", "", "random", nil, 0.0, 1.0, -1.0}
	for _, input := range inputs {
		a := toBool(input)
		b := toBool(input)
		if a != b {
			t.Fatalf("toBool(%v) not deterministic: %v vs %v", input, a, b)
		}
	}
}

// ── Property: applyCallbacks filter-then-validate ordering ──

func TestPropertyCallbacksFilterBeforeValidate(t *testing.T) {
	var order []string

	filter := func(v any) any {
		order = append(order, "filter")
		return v
	}
	validate := func(v any) error {
		order = append(order, "validate")
		return nil
	}

	order = nil
	applyCallbacks("test", validate, filter)

	if len(order) != 2 || order[0] != "filter" || order[1] != "validate" {
		t.Fatalf("expected [filter, validate], got %v", order)
	}
}

// ── Property: applyCallbacks validation error wraps ErrValidation ──

func TestPropertyCallbacksValidationErrorWraps(t *testing.T) {
	validate := func(v any) error {
		return fmt.Errorf("bad value")
	}

	_, err := applyCallbacks("test", validate, nil)
	if err == nil {
		t.Fatal("expected error")
	}
	if !errors.Is(err, ErrValidation) {
		t.Fatalf("error should wrap ErrValidation, got: %v", err)
	}
}

// ── Property: applyCallbacksList with non-slice filter returns original ──

func TestPropertyCallbacksListFilterNonSlice(t *testing.T) {
	filter := func(v any) any {
		return "not a slice"
	}

	input := []any{"a", "b"}
	result, err := applyCallbacksList(input, nil, filter)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 2 || result[0] != "a" {
		t.Fatalf("should keep original when filter returns non-slice, got %v", result)
	}
}

// ── Property: Separator always produces valid JSON regardless of text ──

func TestPropertySeparatorAlwaysValidJSON(t *testing.T) {
	texts := []string{
		"────────",
		"",
		`quotes "inside"`,
		"newline\nin\ntext",
		"\t\ttabs",
		`\backslash`,
		"\x00null byte",
		"emoji 🎉🔥",
		`{"type":"injected"}`,
		string([]byte{0xff, 0xfe}),
	}
	for _, text := range texts {
		s := Separator{Text: text}
		data, err := s.MarshalJSON()
		if err != nil {
			t.Fatalf("MarshalJSON(%q) error: %v", text, err)
		}
		var parsed map[string]any
		if err := json.Unmarshal(data, &parsed); err != nil {
			t.Fatalf("MarshalJSON(%q) produced invalid JSON: %v\nraw: %s", text, err, data)
		}
		if parsed["type"] != "separator" {
			t.Fatalf("type should be separator, got %v", parsed["type"])
		}
	}
}

// ── Cross-component: agent dict keys match protocol spec ──

func TestInvariantAgentDictHasRequiredFields(t *testing.T) {
	testCases := []struct {
		name   string
		setup  func() map[string]any
		expect []string
	}{
		{
			"select",
			func() map[string]any {
				r, w, cleanup := agentSetup(t, `{"answer":"a"}`+"\n")
				defer cleanup()
				Select(SelectConfig{Message: "Q", Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}}})
				lines := readOutput(r, w)
				return lines[1]
			},
			[]string{"type", "message", "choices"},
		},
		{
			"checkbox",
			func() map[string]any {
				r, w, cleanup := agentSetup(t, `{"answer":["a"]}`+"\n")
				defer cleanup()
				Checkbox(CheckboxConfig{Message: "Q", Choices: []ChoiceItem{Choice{Name: "A", Value: "a"}}})
				lines := readOutput(r, w)
				return lines[1]
			},
			[]string{"type", "message", "choices"},
		},
		{
			"number",
			func() map[string]any {
				r, w, cleanup := agentSetup(t, `{"answer":1}`+"\n")
				defer cleanup()
				Number(NumberConfig{Message: "Q"})
				lines := readOutput(r, w)
				return lines[1]
			},
			[]string{"type", "message", "min", "max", "float_allowed"},
		},
		{
			"password",
			func() map[string]any {
				r, w, cleanup := agentSetup(t, `{"answer":"x"}`+"\n")
				defer cleanup()
				Password(PasswordConfig{Message: "Q"})
				lines := readOutput(r, w)
				return lines[1]
			},
			[]string{"type", "message", "mask"},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			dict := tc.setup()
			for _, key := range tc.expect {
				if _, ok := dict[key]; !ok {
					t.Errorf("agent dict for %s missing required key %q. Keys: %v", tc.name, key, keys(dict))
				}
			}
		})
	}
}

func keys(m map[string]any) []string {
	var ks []string
	for k := range m {
		ks = append(ks, k)
	}
	return ks
}
