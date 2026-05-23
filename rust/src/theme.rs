pub struct Theme {
    pub question: &'static str,
    pub success: &'static str,
    pub highlight: &'static str,
    pub selected: &'static str,
    pub answer: &'static str,
    pub error: &'static str,
    pub muted: &'static str,
    pub sym_question: &'static str,
    pub sym_success: &'static str,
    pub sym_pointer: &'static str,
    pub sym_checked: &'static str,
    pub sym_unchecked: &'static str,
}

pub const DEFAULT_THEME: Theme = Theme {
    question: "#9fa4e3",
    success: "#62bfa1",
    highlight: "#90bbe9",
    selected: "#59bca4",
    answer: "#9db9dd",
    error: "#d77780",
    muted: "#84858f",
    sym_question: "?",
    sym_success: "✓",
    sym_pointer: "❯",
    sym_checked: "◉",
    sym_unchecked: "◯",
};

pub const RESET: &str = "\x1b[0m";
pub const BOLD: &str = "\x1b[1m";

pub fn ansi_color(hex: &str) -> String {
    let h = hex.trim_start_matches('#');
    let r = u8::from_str_radix(&h[0..2], 16).unwrap_or(0);
    let g = u8::from_str_radix(&h[2..4], 16).unwrap_or(0);
    let b = u8::from_str_radix(&h[4..6], 16).unwrap_or(0);
    format!("\x1b[38;2;{r};{g};{b}m")
}
