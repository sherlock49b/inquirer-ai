package prompt

import (
	"errors"
	"math"
	"testing"
	"testing/quick"
)

// ── Cross-language consistency tests ──
//
// These tests verify that Go behaves consistently with the Python, Rust and
// TypeScript implementations of inquirer-ai per the shared parity contract.

// ── R2: numeric-string grammar parity ──
//
// All four languages trim ASCII whitespace then require the answer string to
// fully match ^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$ before parsing.

func TestCrossLanguage_NumberGrammarParity(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}

	accept := []string{"1e3", "  5  ", "3.5", "-2", "1E-3", "+7", "0", "42", "1.5e2"}
	for _, in := range accept {
		if _, err := validateNumber(in, cfg); err != nil {
			t.Errorf("grammar must ACCEPT %q, got %v", in, err)
		}
	}

	reject := []string{"1_000", "3abc", "0x10", ".5", "5.", "", "+", "-", "NaN", "Inf", "Infinity"}
	for _, in := range reject {
		if _, err := validateNumber(in, cfg); err == nil {
			t.Errorf("grammar must REJECT %q", in)
		}
	}
}

// ── R4: type-aware value matching parity ──
//
// A JSON string never cross-matches a numeric value, and a bool never matches
// a number, in any language.

func TestCrossLanguage_TypeAwareValueMatching(t *testing.T) {
	cases := []struct {
		answer any
		value  any
		want   bool
	}{
		{"42", 42, false},          // string vs number
		{float64(42), "42", false}, // number vs string
		{true, float64(1), false},  // bool vs number
		{float64(0), false, false}, // number vs bool
		{float64(1), 1, true},      // numeric equality across int/float
		{"x", "x", true},           // string equality
		{true, true, true},         // bool equality
	}
	for _, c := range cases {
		if got := answerMatchesValue(c.answer, c.value); got != c.want {
			t.Errorf("answerMatchesValue(%#v, %#v) = %v, want %v", c.answer, c.value, got, c.want)
		}
	}
}

// ── R4: disabled "" means ENABLED parity ──
//
// A choice is disabled iff Disabled is the bool true OR a non-empty string.

func TestCrossLanguage_DisabledSemantics(t *testing.T) {
	cases := []struct {
		val  any
		want bool // want disabled?
	}{
		{nil, false},
		{false, false},
		{"", false},
		{true, true},
		{"reason", true},
	}
	for _, c := range cases {
		if got := isDisabled(c.val); got != c.want {
			t.Errorf("isDisabled(%#v) = %v, want %v", c.val, got, c.want)
		}
	}
}

// ── FIX B: canonical invalid-choice validation message parity ──
//
// The agent-facing message for an invalid choice must be byte-identical across
// all four languages:
//
//	Invalid choice: <A>. Valid: [<V1>, <V2>, ...]
//
// where <A> is the rejected answer compact-JSON-encoded and each <Vi> is a
// valid value compact-JSON-encoded, joined by ", ".

func TestCrossLanguage_InvalidChoiceMessage(t *testing.T) {
	cases := []struct {
		answer any
		valid  []any
		want   string
	}{
		// Byte-exact examples from the conformance spec.
		{"rs", []any{"py", "go"}, `Invalid choice: "rs". Valid: ["py", "go"]`},
		{1.5, []any{"313", "311"}, `Invalid choice: 1.5. Valid: ["313", "311"]`},
		// expand keys (lowercased) as the valid list.
		{"x", []any{"y", "n"}, `Invalid choice: "x". Valid: ["y", "n"]`},
	}
	for _, c := range cases {
		if got := invalidChoiceMessage(c.answer, c.valid); got != c.want {
			t.Errorf("invalidChoiceMessage(%#v, %#v) = %q, want %q", c.answer, c.valid, got, c.want)
		}
	}
}

// AgentMessage must return the BARE validation text — never the
// "prompt error: validation failed: ..." sentinel wrapper — for every kind of
// validation error, including the already-canonical messages.

func TestCrossLanguage_AgentMessageStripsWrapper(t *testing.T) {
	cases := []struct {
		err  error
		want string
	}{
		{newValidationError(ErrInvalidChoice, `Invalid choice: "rs". Valid: ["py", "go"]`),
			`Invalid choice: "rs". Valid: ["py", "go"]`},
		// Plain wrapped sentinel errors get the framing prefix stripped.
		{errors.New("prompt error: validation failed: Decimal numbers are not allowed"),
			"Decimal numbers are not allowed"},
		{errors.New("prompt error: validation failed: Not a valid number: \"x\""),
			`Not a valid number: "x"`},
		{errors.New("prompt error: validation failed: At least one choice is required"),
			"At least one choice is required"},
	}
	for _, c := range cases {
		if got := AgentMessage(c.err); got != c.want {
			t.Errorf("AgentMessage(%v) = %q, want %q", c.err, got, c.want)
		}
	}
}

// End-to-end: a disabled/invalid select choice emits the canonical
// validation_error message over the protocol, and the re-sent prompt reuses
// the same logical step (FIX A + FIX B together), mirroring conformance P4.

func TestCrossLanguage_SelectInvalidChoiceProtocol(t *testing.T) {
	input := `{"answer":"rs"}` + "\n" + `{"answer":"go"}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	got, err := Select(SelectConfig{
		Message: "Lang",
		Choices: []ChoiceItem{
			Choice{Name: "Python", Value: "py"},
			Choice{Name: "Go", Value: "go"},
			Separator{Text: "--"},
			Choice{Name: "Rust", Value: "rs", Disabled: "soon"},
		},
	})
	lines := readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "go" {
		t.Fatalf("expected \"go\", got %#v", got)
	}

	var verrMsg string
	var promptSteps []float64
	for _, l := range lines {
		switch l["kind"] {
		case "validation_error":
			verrMsg, _ = l["message"].(string)
		case "prompt":
			if s, ok := l["step"].(float64); ok {
				promptSteps = append(promptSteps, s)
			}
		}
	}

	want := `Invalid choice: "rs". Valid: ["py", "go"]`
	if verrMsg != want {
		t.Fatalf("validation_error message = %q, want %q", verrMsg, want)
	}
	if len(promptSteps) != 2 {
		t.Fatalf("expected 2 prompt frames (original + re-send), got %d", len(promptSteps))
	}
	if promptSteps[0] != promptSteps[1] {
		t.Fatalf("re-send reused step? got steps %v, want both equal", promptSteps)
	}
}

// End-to-end: a non-integer rawlist index emits the canonical message
// (replacing the old "index must be an integer, got 1.5"), mirroring P6.

func TestCrossLanguage_RawlistInvalidChoiceProtocol(t *testing.T) {
	input := `{"answer":1.5}` + "\n" + `{"answer":2}` + "\n"
	r, w, cleanup := agentSetup(t, input)
	defer cleanup()

	got, err := Rawlist(RawlistConfig{
		Message: "Ver",
		Choices: []ChoiceItem{
			Choice{Name: "3.13", Value: "313"},
			Separator{Text: "-"},
			Choice{Name: "3.12", Value: "312", Disabled: true},
			Choice{Name: "3.11", Value: "311"},
		},
	})
	lines := readOutput(r, w)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != "311" {
		t.Fatalf("expected \"311\", got %#v", got)
	}

	var verrMsg string
	for _, l := range lines {
		if l["kind"] == "validation_error" {
			verrMsg, _ = l["message"].(string)
		}
	}
	want := `Invalid choice: 1.5. Valid: ["313", "311"]`
	if verrMsg != want {
		t.Fatalf("validation_error message = %q, want %q", verrMsg, want)
	}
}

// ── toBool: cross-language truth table ──

func TestCrossLanguage_toBool(t *testing.T) {
	tests := []struct {
		name   string
		input  any
		expect bool
	}{
		// booleans
		{"true", true, true},
		{"false", false, false},

		// nil
		{"nil", nil, false},

		// float64 zero / nonzero
		{"0.0", 0.0, false},
		{"1.0", 1.0, true},
		{"-1.0", -1.0, true},

		// IEEE-754 special values — all should be false for cross-language
		// consistency (Python: bool(float('nan')) == True, but JS: Boolean(NaN) == false).
		// We align with JS/TS behaviour: NaN → false.
		{"NaN", math.NaN(), false},
		{"Inf", math.Inf(1), false},
		{"-Inf", math.Inf(-1), false},

		// strings — truthy words
		{"empty string", "", false},
		{"y", "y", true},
		{"yes", "yes", true},
		{"n", "n", false},
		{"no", "no", false},
		{"true", "true", true},
		{"false", "false", false},
		{"1", "1", true},
		{"0", "0", false},

		// case-insensitive
		{"YES", "YES", true},
		{"True", "True", true},
		{"Y", "Y", true},
		{"FALSE", "FALSE", false},
		{"No", "No", false},
		{"N", "N", false},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := toBool(tc.input)
			if got != tc.expect {
				t.Errorf("toBool(%v) = %v, want %v (cross-language consistency)", tc.input, got, tc.expect)
			}
		})
	}
}

// ── toBool: non-standard types ──
// In Go toBool returns false for arrays/maps (non-standard types), while
// Python/TS return true for non-empty containers.  Document the Go behaviour.

func TestCrossLanguage_toBool_NonStandardTypes(t *testing.T) {
	tests := []struct {
		name   string
		input  any
		expect bool
	}{
		{"int(1)", 1, false},          // int not handled → falls through to default → false
		{"slice", []int{1, 2}, false}, // Go: false (default branch)
		{"map", map[string]int{"a": 1}, false},
		{"struct", struct{ X int }{1}, false},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := toBool(tc.input)
			if got != tc.expect {
				t.Errorf("toBool(%v) = %v, want %v", tc.input, got, tc.expect)
			}
		})
	}
}

// ── toBool: property — deterministic and case-insensitive ──

func TestCrossLanguage_toBool_PropertyCaseInsensitive(t *testing.T) {
	// "yes" in any case should always return true, "no" always false.
	yesVariants := []string{"yes", "Yes", "YES", "yEs", "yeS", "YeS", "yES", "YEs"}
	for _, s := range yesVariants {
		if !toBool(s) {
			t.Errorf("toBool(%q) = false, want true", s)
		}
	}

	noVariants := []string{"no", "No", "NO", "nO"}
	for _, s := range noVariants {
		if toBool(s) {
			t.Errorf("toBool(%q) = true, want false", s)
		}
	}
}

// ── validateNumber: cross-language consistency ──

func TestCrossLanguage_validateNumber_SpecialValues(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}

	tests := []struct {
		name      string
		input     any
		wantError bool
	}{
		{"NaN", math.NaN(), true},
		{"Inf", math.Inf(1), true},
		{"-Inf", math.Inf(-1), true},
		{"normal int-like", 42.0, false},
		{"normal float", 3.14, false},
		{"zero", 0.0, false},
		{"negative", -7.0, false},
		{"max float64", math.MaxFloat64, false},
		{"smallest positive", math.SmallestNonzeroFloat64, false},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			_, err := validateNumber(tc.input, cfg)
			if tc.wantError && err == nil {
				t.Errorf("validateNumber(%v) should return error", tc.input)
			}
			if !tc.wantError && err != nil {
				t.Errorf("validateNumber(%v) unexpected error: %v", tc.input, err)
			}
			if err != nil && !errors.Is(err, ErrValidation) {
				t.Errorf("validateNumber error should wrap ErrValidation, got: %v", err)
			}
		})
	}
}

func TestCrossLanguage_validateNumber_StringSpecialValues(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}

	tests := []struct {
		name      string
		input     string
		wantError bool
	}{
		{"NaN string", "NaN", true},
		{"Infinity string", "Infinity", true},
		{"-Infinity string", "-Infinity", true},
		{"Inf string", "Inf", true},
		{"-Inf string", "-Inf", true},
		{"normal string", "42", false},
		{"float string", "3.14", false},
		{"negative string", "-7", false},
		{"zero string", "0", false},
		{"scientific", "1e10", false},
		{"empty string", "", true},
		{"not a number", "abc", true},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			_, err := validateNumber(tc.input, cfg)
			if tc.wantError && err == nil {
				t.Errorf("validateNumber(%q) should return error", tc.input)
			}
			if !tc.wantError && err != nil {
				t.Errorf("validateNumber(%q) unexpected error: %v", tc.input, err)
			}
		})
	}
}

func TestCrossLanguage_validateNumber_MinMaxBounds(t *testing.T) {
	min := 0.0
	max := 100.0

	tests := []struct {
		name      string
		value     float64
		wantError bool
	}{
		{"at min", 0.0, false},
		{"at max", 100.0, false},
		{"mid range", 50.0, false},
		{"below min", -0.01, true},
		{"above max", 100.01, true},
		{"way below", -1000.0, true},
		{"way above", 1000.0, true},
	}

	cfg := NumberConfig{Min: &min, Max: &max, FloatAllowed: true}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			_, err := validateNumber(tc.value, cfg)
			if tc.wantError && err == nil {
				t.Errorf("validateNumber(%v) with min=%v max=%v should return error", tc.value, min, max)
			}
			if !tc.wantError && err != nil {
				t.Errorf("validateNumber(%v) with min=%v max=%v unexpected error: %v", tc.value, min, max, err)
			}
		})
	}
}

func TestCrossLanguage_validateNumber_FloatAllowed(t *testing.T) {
	tests := []struct {
		name         string
		value        float64
		floatAllowed bool
		wantError    bool
	}{
		// When FloatAllowed=false, whole numbers are OK (even as float64).
		{"3.0 integer-like, floats disallowed", 3.0, false, false},
		{"3.5 fractional, floats disallowed", 3.5, false, true},
		{"-2.0 integer-like, floats disallowed", -2.0, false, false},
		{"0.0 integer-like, floats disallowed", 0.0, false, false},

		// When FloatAllowed=true, all finite values are OK.
		{"3.5 fractional, floats allowed", 3.5, true, false},
		{"3.0 integer-like, floats allowed", 3.0, true, false},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			cfg := NumberConfig{FloatAllowed: tc.floatAllowed}
			_, err := validateNumber(tc.value, cfg)
			if tc.wantError && err == nil {
				t.Errorf("validateNumber(%v, floatAllowed=%v) should return error", tc.value, tc.floatAllowed)
			}
			if !tc.wantError && err != nil {
				t.Errorf("validateNumber(%v, floatAllowed=%v) unexpected error: %v", tc.value, tc.floatAllowed, err)
			}
		})
	}
}

func TestCrossLanguage_validateNumber_NilInput(t *testing.T) {
	t.Run("nil with default", func(t *testing.T) {
		def := 42.0
		cfg := NumberConfig{Default: &def, FloatAllowed: true}
		result, err := validateNumber(nil, cfg)
		if err != nil {
			t.Fatalf("validateNumber(nil) with default should not error: %v", err)
		}
		if result != 42.0 {
			t.Fatalf("validateNumber(nil) with default = %v, want 42.0", result)
		}
	})

	t.Run("nil without default", func(t *testing.T) {
		cfg := NumberConfig{FloatAllowed: true}
		_, err := validateNumber(nil, cfg)
		if err == nil {
			t.Fatal("validateNumber(nil) without default should return error")
		}
	})
}

func TestCrossLanguage_validateNumber_IntInput(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}
	result, err := validateNumber(42, cfg)
	if err != nil {
		t.Fatalf("validateNumber(int(42)) error: %v", err)
	}
	if result != 42.0 {
		t.Fatalf("validateNumber(int(42)) = %v, want 42.0", result)
	}
}

func TestCrossLanguage_validateNumber_UnsupportedType(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}
	_, err := validateNumber([]int{1, 2, 3}, cfg)
	if err == nil {
		t.Fatal("validateNumber([]int) should return error")
	}
	if !errors.Is(err, ErrValidation) {
		t.Fatalf("error should wrap ErrValidation, got: %v", err)
	}
}

// ── Property: validateNumber rejects all non-finite float64 values ──

func TestCrossLanguage_Property_ValidateNumberRejectsNonFinite(t *testing.T) {
	cfg := NumberConfig{FloatAllowed: true}

	f := func(bits uint64) bool {
		v := math.Float64frombits(bits)
		_, err := validateNumber(v, cfg)
		if math.IsNaN(v) || math.IsInf(v, 0) {
			return err != nil // must reject
		}
		return err == nil // must accept
	}
	if err := quick.Check(f, &quick.Config{MaxCount: 10000}); err != nil {
		t.Fatal(err)
	}
}

// ── Fuzz-style table: toBool edge cases ──

func TestCrossLanguage_toBool_EdgeCases(t *testing.T) {
	// Strings that should be falsy
	falsyStrings := []string{
		"", "0", "false", "n", "no",
		"False", "FALSE", "N", "NO", "nO",
	}
	for _, s := range falsyStrings {
		if toBool(s) {
			t.Errorf("toBool(%q) = true, want false", s)
		}
	}

	// Strings that should be truthy
	truthyStrings := []string{
		"y", "yes", "true", "1",
		"Y", "YES", "TRUE", "True",
	}
	for _, s := range truthyStrings {
		if !toBool(s) {
			t.Errorf("toBool(%q) = false, want true", s)
		}
	}

	// Strings that are neither yes/no/true/false/1/0 should be false
	otherStrings := []string{
		"maybe", "2", "yep", "nope", "oui", "si", "da",
		"  yes  ", "YES!", " ", "truthy", "falsy",
	}
	for _, s := range otherStrings {
		if toBool(s) {
			t.Errorf("toBool(%q) = true, want false (not a recognized truthy string)", s)
		}
	}
}

// ── Property: validateNumber min <= result <= max when no error ──

func TestCrossLanguage_Property_ValidateNumberBoundsHold(t *testing.T) {
	f := func(value float64, lo, hi int16) bool {
		if math.IsNaN(value) || math.IsInf(value, 0) {
			return true // skip
		}
		minVal := float64(lo)
		maxVal := float64(hi)
		if minVal > maxVal {
			return true // skip invalid config
		}
		cfg := NumberConfig{Min: &minVal, Max: &maxVal, FloatAllowed: true}
		result, err := validateNumber(value, cfg)
		if err != nil {
			// should only error when out of bounds
			return value < minVal || value > maxVal
		}
		return result >= minVal && result <= maxVal
	}
	if err := quick.Check(f, &quick.Config{MaxCount: 5000}); err != nil {
		t.Fatal(err)
	}
}
