package prompt

import "encoding/json"

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
	return c.Disabled == nil || c.Disabled == false
}
