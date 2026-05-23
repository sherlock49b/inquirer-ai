use crate::agent::{agent_receive, agent_send};
use crate::choice::{Choice, ChoiceItem};
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{format_success, KeyInput, ListRenderer};
use crate::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use serde_json::{json, Value};

pub struct SelectConfig {
    pub message: String,
    pub choices: Vec<ChoiceItem>,
    pub default: Option<Value>,
    pub page_size: usize,
    pub r#loop: bool,
}

impl SelectConfig {
    pub fn new(message: impl Into<String>, choices: Vec<ChoiceItem>) -> Self {
        Self {
            message: message.into(),
            choices,
            default: None,
            page_size: 10,
            r#loop: true,
        }
    }
}

pub fn select(config: SelectConfig) -> Result<Value> {
    let enabled: Vec<&Choice> = config
        .choices
        .iter()
        .filter_map(|c| match c {
            ChoiceItem::Choice(c) if !c.is_disabled() => Some(c),
            _ => None,
        })
        .collect();

    if enabled.is_empty() {
        return Err(InquirerError::InvalidChoice(
            "choices must contain at least one selectable item".into(),
        ));
    }

    if is_agent_mode() {
        select_agent(&config, &enabled)
    } else {
        select_terminal(&config)
    }
}

fn select_agent(config: &SelectConfig, enabled: &[&Choice]) -> Result<Value> {
    let choices_json: Vec<Value> = config.choices.iter().map(|c| c.to_json()).collect();
    let payload = json!({
        "type": "select",
        "message": config.message,
        "default": config.default,
        "choices": choices_json,
    });
    agent_send(&payload)?;
    let answer = agent_receive()?;

    for c in enabled {
        if answer == c.value || answer.as_str() == Some(&c.name) {
            return Ok(c.value.clone());
        }
    }

    let valid: Vec<&Value> = enabled.iter().map(|c| &c.value).collect();
    Err(InquirerError::Validation(format!(
        "Invalid choice: {answer}. Valid: {valid:?}"
    )))
}

fn select_terminal(config: &SelectConfig) -> Result<Value> {
    let t = &DEFAULT_THEME;
    let indices = selectable_indices(&config.choices);
    if indices.is_empty() {
        return Err(InquirerError::InvalidChoice("No selectable choices".into()));
    }

    let mut cursor = indices[0];
    if let Some(default) = &config.default {
        for (i, item) in config.choices.iter().enumerate() {
            if let ChoiceItem::Choice(c) = item {
                if !c.is_disabled()
                    && (c.value == *default || c.name == default.as_str().unwrap_or(""))
                {
                    cursor = i;
                    break;
                }
            }
        }
    }

    ListRenderer::enable_raw()?;
    let mut renderer = ListRenderer::new();

    loop {
        let header = format!(
            "{}{}{}  {BOLD}{}{RESET}",
            ansi_color(t.question),
            t.sym_question,
            RESET,
            config.message,
        );
        let items = render_items(&config.choices, cursor, config.page_size, t);
        renderer.render(&header, &items);

        match crate::terminal::read_key()? {
            KeyInput::Up | KeyInput::Char('k') => {
                cursor = move_cursor(cursor, -1, &indices, config.r#loop);
            }
            KeyInput::Down | KeyInput::Char('j') => {
                cursor = move_cursor(cursor, 1, &indices, config.r#loop);
            }
            KeyInput::Enter => {
                renderer.clear();
                ListRenderer::disable_raw()?;
                if let ChoiceItem::Choice(c) = &config.choices[cursor] {
                    let display = c.short.as_deref().unwrap_or(&c.name);
                    eprintln!("{}", format_success(&config.message, display));
                    return Ok(c.value.clone());
                }
            }
            KeyInput::CtrlC => {
                renderer.clear();
                ListRenderer::disable_raw()?;
                return Err(InquirerError::PromptAborted(
                    "Prompt aborted by user".into(),
                ));
            }
            _ => {}
        }
    }
}

fn selectable_indices(choices: &[ChoiceItem]) -> Vec<usize> {
    choices
        .iter()
        .enumerate()
        .filter_map(|(i, c)| match c {
            ChoiceItem::Choice(c) if !c.is_disabled() => Some(i),
            _ => None,
        })
        .collect()
}

fn move_cursor(current: usize, direction: i32, indices: &[usize], do_loop: bool) -> usize {
    let pos = indices.iter().position(|&i| i == current).unwrap_or(0);
    let new_pos = pos as i32 + direction;
    if do_loop {
        let len = indices.len() as i32;
        indices[((new_pos % len + len) % len) as usize]
    } else {
        let clamped = new_pos.max(0).min(indices.len() as i32 - 1) as usize;
        indices[clamped]
    }
}

fn render_items(
    choices: &[ChoiceItem],
    cursor: usize,
    page_size: usize,
    t: &crate::theme::Theme,
) -> Vec<(String, String)> {
    let total = choices.len();
    let ps = page_size.min(total);
    let start = cursor.saturating_sub(ps / 2).min(total.saturating_sub(ps));
    let end = (start + ps).min(total);

    let mut items = Vec::new();
    let mc = ansi_color(t.muted);

    if start > 0 {
        items.push((mc.clone(), "  (more above)".to_string()));
    }

    for (i, choice) in choices.iter().enumerate().take(end).skip(start) {
        match choice {
            ChoiceItem::Separator(s) => {
                items.push((mc.clone(), format!("  {}", s.text)));
            }
            ChoiceItem::Choice(c) if c.is_disabled() => {
                let reason = c
                    .disabled_reason()
                    .map(|r| format!(" ({r})"))
                    .unwrap_or_default();
                items.push((mc.clone(), format!("  {}{reason} (disabled)", c.name)));
            }
            ChoiceItem::Choice(c) if i == cursor => {
                let hc = ansi_color(t.highlight);
                let desc = c
                    .description
                    .as_ref()
                    .map(|d| format!(" - {d}"))
                    .unwrap_or_default();
                items.push((hc, format!("{} {}{desc}", t.sym_pointer, c.name)));
            }
            ChoiceItem::Choice(c) => {
                items.push((String::new(), format!("  {}", c.name)));
            }
        }
    }

    if end < total {
        items.push((mc, "  (more below)".to_string()));
    }

    items
}
