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
    pub required: bool,
}

impl CheckboxConfig {
    pub fn new(message: impl Into<String>, choices: Vec<ChoiceItem>) -> Self {
        Self {
            message: message.into(),
            choices,
            default: Vec::new(),
            page_size: 10,
            r#loop: true,
            required: false,
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

    let required = config.required;
    agent_prompt_with_retry(&payload, move |answer| {
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
            // Type-aware value match (string "42" != number 42, etc.) OR an
            // exact string match against a choice name.
            if valid_values.contains(v) {
                result.push(v.clone());
            } else if let Some(name) = v.as_str().filter(|n| valid_names.contains(n)) {
                let choice = enabled
                    .iter()
                    .find(|c| c.name == name)
                    .expect("name is in valid_names");
                result.push(choice.value.clone());
            } else {
                let valid = enabled.iter().map(|c| &c.value);
                return Err(InquirerError::Validation(
                    crate::prompts::invalid_choice_message(v, valid),
                ));
            }
        }

        if required && result.is_empty() {
            return Err(InquirerError::Validation(
                "At least one choice is required".into(),
            ));
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
            KeyInput::Char(c @ '1'..='9') => {
                let n = (c as usize) - ('0' as usize);
                let target = if n >= indices.len() {
                    indices.len() - 1
                } else {
                    n - 1
                };
                cursor = indices[target];
            }
            KeyInput::Enter => {
                if config.required && checked.is_empty() {
                    continue;
                }
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::choice::Separator;
    use serde_json::json;

    fn make_choices(names: &[&str]) -> Vec<ChoiceItem> {
        names
            .iter()
            .map(|n| ChoiceItem::Choice(Choice::new(*n, json!(*n))))
            .collect()
    }

    // -- selectable_indices --

    #[test]
    fn selectable_indices_all_enabled() {
        let choices = make_choices(&["A", "B", "C"]);
        assert_eq!(selectable_indices(&choices), vec![0, 1, 2]);
    }

    #[test]
    fn selectable_indices_with_separator_and_disabled() {
        let mut choices = make_choices(&["A", "B", "C"]);
        choices.insert(1, ChoiceItem::Separator(Separator::new("---")));
        if let ChoiceItem::Choice(ref mut c) = choices[3] {
            // "C" is now at index 3
            c.disabled = Some(json!(true));
        }
        // 0=A(ok), 1=sep(skip), 2=B(ok), 3=C(disabled)
        assert_eq!(selectable_indices(&choices), vec![0, 2]);
    }

    // -- move_cursor --

    #[test]
    fn move_cursor_wraps_with_loop() {
        let indices = vec![0, 2, 4];
        assert_eq!(move_cursor(4, 1, &indices, true), 0);
        assert_eq!(move_cursor(0, -1, &indices, true), 4);
    }

    #[test]
    fn move_cursor_clamps_without_loop() {
        let indices = vec![0, 2, 4];
        assert_eq!(move_cursor(4, 1, &indices, false), 4);
        assert_eq!(move_cursor(0, -1, &indices, false), 0);
    }

    // -- render_items --

    #[test]
    fn render_items_unchecked_at_cursor() {
        let choices = make_choices(&["A", "B"]);
        let t = &DEFAULT_THEME;
        let checked = BTreeSet::new();
        let items = render_items(&choices, 0, &checked, 10, t);
        // At cursor: should have pointer and unchecked symbol
        assert!(items[0].1.contains(t.sym_pointer));
        assert!(items[0].1.contains(t.sym_unchecked));
        assert!(items[0].1.contains("A"));
    }

    #[test]
    fn render_items_checked_at_cursor() {
        let choices = make_choices(&["A", "B"]);
        let t = &DEFAULT_THEME;
        let mut checked = BTreeSet::new();
        checked.insert(0);
        let items = render_items(&choices, 0, &checked, 10, t);
        assert!(items[0].1.contains(t.sym_pointer));
        assert!(items[0].1.contains(t.sym_checked));
    }

    #[test]
    fn render_items_checked_not_at_cursor() {
        let choices = make_choices(&["A", "B"]);
        let t = &DEFAULT_THEME;
        let mut checked = BTreeSet::new();
        checked.insert(1);
        let items = render_items(&choices, 0, &checked, 10, t);
        // B is checked but not at cursor
        assert!(items[1].1.contains(t.sym_checked));
        assert!(!items[1].1.contains(t.sym_pointer));
        // Style should use selected colour
        let selected_colour = ansi_color(t.selected);
        assert_eq!(items[1].0, selected_colour);
    }

    #[test]
    fn render_items_unchecked_not_at_cursor() {
        let choices = make_choices(&["A", "B"]);
        let t = &DEFAULT_THEME;
        let checked = BTreeSet::new();
        let items = render_items(&choices, 0, &checked, 10, t);
        // B is unchecked and not at cursor
        assert!(items[1].1.contains(t.sym_unchecked));
        assert_eq!(items[1].0, "");
    }

    #[test]
    fn render_items_disabled_shows_unchecked_and_disabled() {
        let mut c = Choice::new("Off", json!("off"));
        c.disabled = Some(json!("nope"));
        let choices = vec![
            ChoiceItem::Choice(Choice::new("On", json!("on"))),
            ChoiceItem::Choice(c),
        ];
        let t = &DEFAULT_THEME;
        let checked = BTreeSet::new();
        let items = render_items(&choices, 0, &checked, 10, t);
        assert!(items[1].1.contains("disabled"));
        assert!(items[1].1.contains("nope"));
        assert!(items[1].1.contains(t.sym_unchecked));
    }

    #[test]
    fn render_items_separator() {
        let mut choices = make_choices(&["A"]);
        choices.insert(0, ChoiceItem::Separator(Separator::new("Group")));
        let t = &DEFAULT_THEME;
        let checked = BTreeSet::new();
        let items = render_items(&choices, 1, &checked, 10, t);
        assert!(items[0].1.contains("Group"));
    }

    #[test]
    fn render_items_pagination_more_above_below() {
        let choices = make_choices(&["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]);
        let t = &DEFAULT_THEME;
        let checked = BTreeSet::new();
        let items = render_items(&choices, 5, &checked, 3, t);
        let texts: Vec<&str> = items.iter().map(|(_, t)| t.as_str()).collect();
        assert!(texts.iter().any(|t| t.contains("more above")));
        assert!(texts.iter().any(|t| t.contains("more below")));
    }

    #[test]
    fn render_items_cursor_uses_highlight() {
        let choices = make_choices(&["X"]);
        let t = &DEFAULT_THEME;
        let checked = BTreeSet::new();
        let items = render_items(&choices, 0, &checked, 10, t);
        let highlight = ansi_color(t.highlight);
        assert_eq!(items[0].0, highlight);
    }
}
