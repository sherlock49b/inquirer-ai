package prompt

type Theme struct {
	SymQuestion  string
	SymSuccess   string
	SymPointer   string
	SymChecked   string
	SymUnchecked string
}

var DefaultTheme = Theme{
	SymQuestion:  "?",
	SymSuccess:   "✓",
	SymPointer:   "❯",
	SymChecked:   "◉",
	SymUnchecked: "◯",
}
