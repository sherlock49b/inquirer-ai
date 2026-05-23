package prompt

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

func (s Separator) MarshalJSON() ([]byte, error) {
	return []byte(`{"type":"separator","text":"` + s.Text + `"}`), nil
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
