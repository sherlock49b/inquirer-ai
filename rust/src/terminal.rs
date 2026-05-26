use crate::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use crossterm::cursor;
use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyModifiers};
use crossterm::{queue, terminal};
use std::io::{self, BufRead, Write};

pub fn read_line(prompt: &str) -> io::Result<String> {
    read_line_with_default(prompt, None)
}

pub fn read_line_with_default(prompt: &str, prefill: Option<&str>) -> io::Result<String> {
    match prefill {
        Some(default) => {
            eprint!("{prompt}{default}");
            io::stderr().flush()?;
            let mut line = String::new();
            io::stdin().lock().read_line(&mut line)?;
            let trimmed = line
                .trim_end_matches('\n')
                .trim_end_matches('\r')
                .to_string();
            if trimmed.is_empty() {
                Ok(default.to_string())
            } else {
                Ok(trimmed)
            }
        }
        None => {
            eprint!("{prompt}");
            io::stderr().flush()?;
            let mut line = String::new();
            io::stdin().lock().read_line(&mut line)?;
            Ok(line
                .trim_end_matches('\n')
                .trim_end_matches('\r')
                .to_string())
        }
    }
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
    Backspace,
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
                KeyCode::Backspace => KeyInput::Backspace,
                KeyCode::Char(' ') => KeyInput::Space,
                KeyCode::Char(c) => KeyInput::Char(c),
                _ => KeyInput::Other,
            });
        }
    }
}

/// Poll for a key event with a timeout. Returns `None` if no event is
/// available within `timeout`.
pub fn poll_key(timeout: std::time::Duration) -> io::Result<Option<KeyInput>> {
    if event::poll(timeout)? {
        Ok(Some(read_key()?))
    } else {
        Ok(None)
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
            let _ = queue!(stderr, cursor::RestorePosition);
        }
        let _ = queue!(
            stderr,
            cursor::SavePosition,
            terminal::Clear(terminal::ClearType::FromCursorDown)
        );
        let _ = write!(stderr, "{header}");
        for (style, text) in items {
            let _ = write!(stderr, "\r\n{style}{text}{RESET}");
        }
        self.rendered_lines = 1 + items.len();
        let _ = stderr.flush();
    }

    pub fn clear(&self) {
        let mut stderr = io::stderr().lock();
        if self.rendered_lines > 0 {
            let _ = queue!(
                stderr,
                cursor::RestorePosition,
                terminal::Clear(terminal::ClearType::FromCursorDown)
            );
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
