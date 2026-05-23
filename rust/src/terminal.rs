use crate::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyModifiers};
use crossterm::terminal;
use std::io::{self, BufRead, Write};

pub fn read_line(prompt: &str) -> io::Result<String> {
    eprint!("{prompt}");
    io::stderr().flush()?;
    let mut line = String::new();
    io::stdin().lock().read_line(&mut line)?;
    Ok(line
        .trim_end_matches('\n')
        .trim_end_matches('\r')
        .to_string())
}

pub fn format_question(message: &str, suffix: &str) -> String {
    let t = &DEFAULT_THEME;
    let c = ansi_color(t.question);
    format!(
        "{c}{}{RESET} {BOLD}{message}{suffix}:{RESET} ",
        t.sym_question
    )
}

pub fn format_success(message: &str, answer: &str) -> String {
    let t = &DEFAULT_THEME;
    let sc = ansi_color(t.success);
    let ac = ansi_color(t.answer);
    format!("{sc}{}{RESET} {message} {ac}{answer}{RESET}", t.sym_success)
}

pub fn format_error(msg: &str) -> String {
    let ec = ansi_color(DEFAULT_THEME.error);
    format!("{ec}  {msg}{RESET}")
}

pub enum KeyInput {
    Up,
    Down,
    Enter,
    Space,
    Char(char),
    CtrlC,
    Other,
}

pub fn read_key() -> io::Result<KeyInput> {
    loop {
        if let Event::Key(KeyEvent {
            code, modifiers, ..
        }) = event::read()?
        {
            if modifiers.contains(KeyModifiers::CONTROL) && code == KeyCode::Char('c') {
                return Ok(KeyInput::CtrlC);
            }
            return Ok(match code {
                KeyCode::Up => KeyInput::Up,
                KeyCode::Down => KeyInput::Down,
                KeyCode::Enter => KeyInput::Enter,
                KeyCode::Char(' ') => KeyInput::Space,
                KeyCode::Char(c) => KeyInput::Char(c),
                _ => KeyInput::Other,
            });
        }
    }
}

#[derive(Default)]
pub struct ListRenderer {
    rendered_lines: usize,
}

impl ListRenderer {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn render(&mut self, header: &str, items: &[(String, String)]) {
        let mut stderr = io::stderr().lock();
        if self.rendered_lines > 0 {
            let _ = write!(stderr, "\x1b[{}A", self.rendered_lines);
        }
        let _ = writeln!(stderr, "\x1b[2K{header}");
        for (style, text) in items {
            let _ = writeln!(stderr, "\x1b[2K{style}{text}{RESET}");
        }
        let total = 1 + items.len();
        if self.rendered_lines > total {
            for _ in total..self.rendered_lines {
                let _ = writeln!(stderr, "\x1b[2K");
            }
            let _ = write!(stderr, "\x1b[{}A", self.rendered_lines - total);
        }
        self.rendered_lines = total;
        let _ = stderr.flush();
    }

    pub fn clear(&self) {
        let mut stderr = io::stderr().lock();
        if self.rendered_lines > 0 {
            let _ = write!(stderr, "\x1b[{}A", self.rendered_lines);
            for _ in 0..self.rendered_lines {
                let _ = writeln!(stderr, "\x1b[2K");
            }
            let _ = write!(stderr, "\x1b[{}A", self.rendered_lines);
        }
        let _ = stderr.flush();
    }

    pub fn enable_raw() -> io::Result<()> {
        terminal::enable_raw_mode()?;
        eprint!("\x1b[?25l");
        io::stderr().flush()?;
        Ok(())
    }

    pub fn disable_raw() -> io::Result<()> {
        terminal::disable_raw_mode()?;
        eprint!("\x1b[?25h");
        io::stderr().flush()?;
        Ok(())
    }
}
