package prompt

import (
	"encoding/json"
	"strings"
)

// jsonCompact returns the compact JSON encoding of v (the canonical cross-
// language representation of a value). A string "rs" becomes the 4 bytes
// "rs" WITH double quotes; a number 1.5 becomes 1.5; etc. On a marshal error
// it falls back to an empty string rather than panicking.
func jsonCompact(v any) string {
	b, err := json.Marshal(v)
	if err != nil {
		return ""
	}
	return string(b)
}

// invalidChoiceMessage builds the canonical, byte-identical-across-languages
// validation message for a rejected choice:
//
//	Invalid choice: <A>. Valid: [<V1>, <V2>, ...]
//
// where <A> is the rejected answer compact-JSON-encoded and each <Vi> is a
// valid value compact-JSON-encoded, joined by ", ".
func invalidChoiceMessage(answer any, validValues []any) string {
	parts := make([]string, len(validValues))
	for i, v := range validValues {
		parts[i] = jsonCompact(v)
	}
	return "Invalid choice: " + jsonCompact(answer) + ". Valid: [" + strings.Join(parts, ", ") + "]"
}

// Choice represents a selectable option in list-based prompts.
type Choice struct {
	Name        string `json:"name"`
	Value       any    `json:"value"`
	Disabled    any    `json:"disabled,omitempty"`
	Short       string `json:"short,omitempty"`
	Description string `json:"description,omitempty"`
}

// Separator is a non-selectable divider line in choice lists.
type Separator struct {
	Text string `json:"text"`
}

// MarshalJSON serializes a Separator with a "type":"separator" field.
func (s Separator) MarshalJSON() ([]byte, error) {
	return json.Marshal(struct {
		Type string `json:"type"`
		Text string `json:"text"`
	}{Type: "separator", Text: s.Text})
}

// ChoiceItem is the interface implemented by Choice and Separator.
type ChoiceItem interface {
	isChoiceItem()
}

func (c Choice) isChoiceItem()    {}
func (s Separator) isChoiceItem() {}

// IsSelectable returns true if the item is an enabled Choice (not a Separator or disabled).
func IsSelectable(item ChoiceItem) bool {
	c, ok := item.(Choice)
	if !ok {
		return false
	}
	return !isDisabled(c.Disabled)
}

// answerMatchesValue reports whether a decoded JSON answer matches a choice's
// value in a TYPE-AWARE way: same JSON type and value. A JSON string "42" does
// NOT match a numeric value 42, and a boolean never matches a number. Numeric
// equality treats Go int/float values as the same JSON number when their value
// is equal (e.g. value int(1) matches answer 1.0). No string coercion is done.
func answerMatchesValue(answer, value any) bool {
	switch a := answer.(type) {
	case string:
		s, ok := value.(string)
		return ok && a == s
	case bool:
		b, ok := value.(bool)
		return ok && a == b
	case float64:
		f, ok := toFloat(value)
		return ok && a == f
	case nil:
		return value == nil
	default:
		// Composite types (slices/maps): fall back to JSON equality.
		return jsonEqual(answer, value)
	}
}

// matchesChoice reports whether a decoded JSON answer matches a resolved
// choice, per the parity contract: a type-aware value match OR a string answer
// exactly equal to the choice's name. Disabled choices are never matched here;
// callers are expected to skip them.
func matchesChoice(answer any, c resolvedChoice) bool {
	if answerMatchesValue(answer, c.value) {
		return true
	}
	if s, ok := answer.(string); ok && s == c.name {
		return true
	}
	return false
}

// toFloat returns the float64 value of a numeric Go value and whether it was
// numeric. Booleans are explicitly NOT numeric.
func toFloat(v any) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int8:
		return float64(n), true
	case int16:
		return float64(n), true
	case int32:
		return float64(n), true
	case int64:
		return float64(n), true
	case uint:
		return float64(n), true
	case uint8:
		return float64(n), true
	case uint16:
		return float64(n), true
	case uint32:
		return float64(n), true
	case uint64:
		return float64(n), true
	default:
		return 0, false
	}
}

func jsonEqual(a, b any) bool {
	ab, errA := json.Marshal(a)
	bb, errB := json.Marshal(b)
	if errA != nil || errB != nil {
		return false
	}
	return string(ab) == string(bb)
}

// isDisabled reports whether a choice's Disabled field marks it disabled.
// Per the parity contract, a choice is disabled iff Disabled is the boolean
// true OR a non-empty string. false, nil/absent, and "" mean ENABLED.
func isDisabled(d any) bool {
	switch v := d.(type) {
	case bool:
		return v
	case string:
		return v != ""
	case nil:
		return false
	default:
		// Any other non-nil value (e.g. number) is treated as enabled to
		// match the majority behaviour across languages.
		return false
	}
}
