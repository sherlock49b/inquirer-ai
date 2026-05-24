package prompt

import (
	"errors"
	"math"
	"testing"
	"testing/quick"
)

// ── Cross-language consistency tests ──
//
// These tests verify that Go behaves consistently with the Python and
// TypeScript implementations of inquirer-ai.  Where the Go code currently
// diverges, the test is expected to FAIL, documenting the bug.

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
