package prompt

type Choice struct {
	Name        string `json:"name"`
	Value       any    `json:"value"`
	Disabled    any    `json:"disabled,omitempty"`
	Short       string `json:"short,omitempty"`
	Description string `json:"description,omitempty"`
}

type Separator struct {
	Text string `json:"text"`
}

func (s Separator) MarshalJSON() ([]byte, error) {
	return []byte(`{"type":"separator","text":"` + s.Text + `"}`), nil
}

type ChoiceItem interface {
	isChoiceItem()
}

func (c Choice) isChoiceItem()    {}
func (s Separator) isChoiceItem() {}

func IsSelectable(item ChoiceItem) bool {
	c, ok := item.(Choice)
	if !ok {
		return false
	}
	return c.Disabled == nil || c.Disabled == false
}
