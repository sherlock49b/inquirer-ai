package prompt

import (
	"encoding/json"
	"math"
	"testing"
	"unicode/utf8"
)

// ── Fuzz: validateNumber with random inputs ──

func FuzzValidateNumber(f *testing.F) {
	f.Add(42.0)
	f.Add(0.0)
	f.Add(-1.0)
	f.Add(3.14)
	f.Add(math.MaxFloat64)
	f.Add(-math.MaxFloat64)
	f.Add(math.SmallestNonzeroFloat64)

	f.Fuzz(func(t *testing.T, v float64) {
		if math.IsNaN(v) || math.IsInf(v, 0) {
			t.Skip()
		}
		cfg := NumberConfig{FloatAllowed: true}
		result, err := validateNumber(v, cfg)
		if err != nil {
			t.Fatalf("validateNumber(%v) should accept any finite float, got error: %v", v, err)
		}
		if result != v {
			t.Fatalf("validateNumber(%v) = %v, want %v", v, result, v)
		}
	})
}

func FuzzValidateNumberString(f *testing.F) {
	f.Add("42")
	f.Add("3.14")
	f.Add("-0")
	f.Add("0.0")
	f.Add("")
	f.Add("abc")
	f.Add("1e308")
	f.Add("NaN")
	f.Add("Infinity")

	f.Fuzz(func(t *testing.T, s string) {
		cfg := NumberConfig{FloatAllowed: true}
		result, err := validateNumber(s, cfg)
		if err != nil {
			return
		}
		if math.IsNaN(result) || math.IsInf(result, 0) {
			t.Fatalf("validateNumber(%q) returned %v — should reject non-finite", s, result)
		}
	})
}

// ── Fuzz: Separator.MarshalJSON with arbitrary text ──

func FuzzSeparatorMarshalJSON(f *testing.F) {
	f.Add("────────")
	f.Add("")
	f.Add(`he said "hello"`)
	f.Add("line1\nline2")
	f.Add(`back\slash`)
	f.Add("\x00\x01\x02")
	f.Add("emoji 🔥")
	f.Add(`{"injected": true}`)

	f.Fuzz(func(t *testing.T, text string) {
		s := Separator{Text: text}
		data, err := s.MarshalJSON()
		if err != nil {
			t.Fatalf("MarshalJSON failed: %v", err)
		}

		var parsed map[string]any
		if err := json.Unmarshal(data, &parsed); err != nil {
			t.Fatalf("MarshalJSON produced invalid JSON for text %q: %v\nJSON: %s", text, err, data)
		}

		if parsed["type"] != "separator" {
			t.Fatalf("type field should be 'separator', got %v", parsed["type"])
		}
		if utf8.ValidString(text) && parsed["text"] != text {
			t.Fatalf("text roundtrip failed: input %q, got %q", text, parsed["text"])
		}
	})
}

// ── Fuzz: AgentReceive with arbitrary JSON ──

func FuzzAgentReceiveJSON(f *testing.F) {
	f.Add(`{"answer": "hello"}`)
	f.Add(`{"answer": 42}`)
	f.Add(`{"answer": true}`)
	f.Add(`{"answer": null}`)
	f.Add(`{"answer": [1,2,3]}`)
	f.Add(`{"value": "no answer key"}`)
	f.Add(`not json`)
	f.Add(`""`)
	f.Add(`[]`)
	f.Add(`null`)
	f.Add(`{}`)

	f.Fuzz(func(t *testing.T, input string) {
		// just verify it doesn't panic — errors are expected
		defer func() {
			if r := recover(); r != nil {
				t.Fatalf("AgentReceive panicked on input %q: %v", input, r)
			}
		}()

		r, w, cleanup := agentSetup(t, input+"\n")
		defer cleanup()
		AgentReceive()
		readOutput(r, w)
	})
}
