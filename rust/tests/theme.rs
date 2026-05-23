use inquirer_ai::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};

#[test]
fn ansi_color_red() {
    assert_eq!(ansi_color("#ff0000"), "\x1b[38;2;255;0;0m");
}

#[test]
fn ansi_color_green() {
    assert_eq!(ansi_color("#00ff00"), "\x1b[38;2;0;255;0m");
}

#[test]
fn ansi_color_without_hash() {
    assert_eq!(ansi_color("0000ff"), "\x1b[38;2;0;0;255m");
}

#[test]
fn default_theme_symbols() {
    assert_eq!(DEFAULT_THEME.sym_question, "?");
    assert_eq!(DEFAULT_THEME.sym_success, "✓");
    assert_eq!(DEFAULT_THEME.sym_pointer, "❯");
    assert_eq!(DEFAULT_THEME.sym_checked, "◉");
    assert_eq!(DEFAULT_THEME.sym_unchecked, "◯");
}

#[test]
fn reset_and_bold() {
    assert_eq!(RESET, "\x1b[0m");
    assert_eq!(BOLD, "\x1b[1m");
}
