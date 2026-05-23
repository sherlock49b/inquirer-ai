package prompt

// Theme controls the symbols used in terminal prompt rendering.
type Theme struct {
	SymQuestion  string
	SymSuccess   string
	SymPointer   string
	SymChecked   string
	SymUnchecked string
}

// DefaultTheme is the default set of symbols for prompt rendering.
var DefaultTheme = Theme{
	SymQuestion:  "?",
	SymSuccess:   "✓",
	SymPointer:   "❯",
	SymChecked:   "◉",
	SymUnchecked: "◯",
}
