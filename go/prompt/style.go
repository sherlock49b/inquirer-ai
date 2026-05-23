package prompt

import "github.com/charmbracelet/lipgloss"

var (
	styleQuestion  = lipgloss.NewStyle().Foreground(lipgloss.Color("#9fa4e3")).Bold(true)
	styleSuccess   = lipgloss.NewStyle().Foreground(lipgloss.Color("#62bfa1")).Bold(true)
	stylePointer   = lipgloss.NewStyle().Foreground(lipgloss.Color("#9c99ec")).Bold(true)
	styleHighlight = lipgloss.NewStyle().Foreground(lipgloss.Color("#90bbe9")).Bold(true)
	styleSelected  = lipgloss.NewStyle().Foreground(lipgloss.Color("#59bca4"))
	styleAnswer    = lipgloss.NewStyle().Foreground(lipgloss.Color("#9db9dd"))
	styleError     = lipgloss.NewStyle().Foreground(lipgloss.Color("#d77780"))
	styleMuted     = lipgloss.NewStyle().Foreground(lipgloss.Color("#84858f"))
)

func renderQuestion(message string) string {
	return styleQuestion.Render(DefaultTheme.SymQuestion) + " " + lipgloss.NewStyle().Bold(true).Render(message)
}

func renderSuccess(message, answer string) string {
	return styleSuccess.Render(DefaultTheme.SymSuccess) + " " + message + " " + styleAnswer.Render(answer)
}

func renderError(text string) string {
	return styleError.Render("  " + text)
}
