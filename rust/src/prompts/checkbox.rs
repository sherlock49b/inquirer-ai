use crate::agent::agent_prompt_with_retry;
use crate::choice::{Choice, ChoiceItem};
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{format_success, KeyInput, ListRenderer};
use crate::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use serde_json::{json, Value};
use std::collections::BTreeSet;

pub struct CheckboxConfig {
    pub message: String,
    pub choices: Vec<ChoiceItem>,
    pub default: Vec<Value>,
    pub page_size: usize,
    pub r#loop: bool,
}

impl CheckboxConfig {
    pub fn new(message: impl Into<String>, choices: Vec<ChoiceItem>) -> Self {
        Self {
            message: message.into(),
            choices,
            default: Vec::new(),
            page_size: 10,
            r#loop: true,
        }
    }
}

pub fn checkbox(config: CheckboxConfig) -> Result<Vec<Value>> {
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
        checkbox_agent(&config, &enabled)
    } else {
        checkbox_terminal(&config)
    }
}

fn checkbox_agent(config: &CheckboxConfig, enabled: &[&Choice]) -> Result<Vec<Value>> {
    let choices_json: Vec<Value> = config.choices.iter().map(|c| c.to_json()).collect();
    let payload = json!({
        "type": "checkbox",
        "message": config.message,
        "default": config.default,
        "choices": choices_json,
    });

    agent_prompt_with_retry(&payload, |answer| {
        let arr = match answer.as_array() {
            Some(a) => a,
            None => {
                return Err(InquirerError::Validation(format!(
                    "Expected an array, got {answer}"
                )));
            }
        };

        let valid_values: std::collections::HashSet<&Value> =
            enabled.iter().map(|c| &c.value).collect();
        let valid_names: std::collections::HashSet<&str> =
            enabled.iter().map(|c| c.name.as_str()).collect();

        let mut result = Vec::new();
        for v in arr {
            if valid_values.contains(v) {
                result.push(v.clone());
            } else if let Some(name) = v.as_str() {
                if valid_names.contains(name) {
                    let choice = enabled.iter().find(|c| c.name == name).unwrap();
                    result.push(choice.value.clone());
                } else {
                    return Err(InquirerError::Validation(format!(
                        "Invalid choice: {v}. Valid: {valid_values:?}"
                    )));
                }
            } else {
                return Err(InquirerError::Validation(format!("Invalid choice: {v}")));
            }
        }

        Ok(result)
    })
}

fn checkbox_terminal(config: &CheckboxConfig) -> Result<Vec<Value>> {
    let t = &DEFAULT_THEME;
    let indices = selectable_indices(&config.choices);
    if indices.is_empty() {
        return Err(InquirerError::InvalidChoice("No selectable choices".into()));
    }

    let mut cursor = indices[0];
    let mut checked = BTreeSet::new();

    for (i, item) in config.choices.iter().enumerate() {
        if let ChoiceItem::Choice(c) = item {
            if !c.is_disabled() && config.default.contains(&c.value) {
                checked.insert(i);
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
        let items = render_items(&config.choices, cursor, &checked, config.page_size, t);
        renderer.render(&header, &items);

        match crate::terminal::read_key()? {
            KeyInput::Up | KeyInput::Char('k') => {
                cursor = move_cursor(cursor, -1, &indices, config.r#loop);
            }
            KeyInput::Down | KeyInput::Char('j') => {
                cursor = move_cursor(cursor, 1, &indices, config.r#loop);
            }
            KeyInput::Space if indices.contains(&cursor) => {
                if checked.contains(&cursor) {
                    checked.remove(&cursor);
                } else {
                    checked.insert(cursor);
                }
            }
            KeyInput::Char('a') => {
                if checked.len() == indices.len() {
                    checked.clear();
                } else {
                    for &i in &indices {
                        checked.insert(i);
                    }
                }
            }
            KeyInput::Enter => {
                renderer.clear();
                ListRenderer::disable_raw()?;
                let result: Vec<Value> = checked
                    .iter()
                    .filter_map(|&i| match &config.choices[i] {
                        ChoiceItem::Choice(c) => Some(c.value.clone()),
                        _ => None,
                    })
                    .collect();
                let names: Vec<&str> = checked
                    .iter()
                    .filter_map(|&i| match &config.choices[i] {
                        ChoiceItem::Choice(c) => {
                            Some(c.short.as_deref().unwrap_or(c.name.as_str()))
                        }
                        _ => None,
                    })
                    .collect();
                let display = if names.is_empty() {
                    "none".to_string()
                } else {
                    names.join(", ")
                };
                eprintln!("{}", format_success(&config.message, &display));
                return Ok(result);
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
    checked: &BTreeSet<usize>,
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
                items.push((
                    mc.clone(),
                    format!("  {} {}{reason} (disabled)", t.sym_unchecked, c.name),
                ));
            }
            ChoiceItem::Choice(c) => {
                let arrow = if i == cursor { t.sym_pointer } else { " " };
                let mark = if checked.contains(&i) {
                    t.sym_checked
                } else {
                    t.sym_unchecked
                };
                let style = if i == cursor {
                    ansi_color(t.highlight)
                } else if checked.contains(&i) {
                    ansi_color(t.selected)
                } else {
                    String::new()
                };
                items.push((style, format!("{arrow} {mark} {}", c.name)));
            }
        }
    }

    if end < total {
        items.push((mc, "  (more below)".to_string()));
    }

    items
}
