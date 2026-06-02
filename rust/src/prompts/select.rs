use crate::agent::agent_prompt_with_retry;
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

    agent_prompt_with_retry(&payload, |answer| {
        for c in enabled {
            if answer == c.value || answer.as_str() == Some(&c.name) {
                return Ok(c.value.clone());
            }
        }
        let valid = enabled.iter().map(|c| &c.value);
        Err(InquirerError::Validation(
            crate::prompts::invalid_choice_message(&answer, valid),
        ))
    })
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
            KeyInput::Char(c @ '1'..='9') => {
                let n = (c as usize) - ('0' as usize);
                let target = if n >= indices.len() {
                    indices.len() - 1
                } else {
                    n - 1
                };
                cursor = indices[target];
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
                    .map(|d| {
                        let clean: String =
                            d.chars().filter(|c| !matches!(c, '\n' | '\r')).collect();
                        format!(" - {clean}")
                    })
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
    fn selectable_indices_with_separator() {
        let mut choices = make_choices(&["A", "B"]);
        choices.insert(1, ChoiceItem::Separator(Separator::new("---")));
        // indices: 0=A, 1=sep, 2=B
        assert_eq!(selectable_indices(&choices), vec![0, 2]);
    }

    #[test]
    fn selectable_indices_with_disabled() {
        let mut choices = make_choices(&["A", "B", "C"]);
        if let ChoiceItem::Choice(ref mut c) = choices[1] {
            c.disabled = Some(json!(true));
        }
        assert_eq!(selectable_indices(&choices), vec![0, 2]);
    }

    #[test]
    fn selectable_indices_empty() {
        let choices: Vec<ChoiceItem> = vec![ChoiceItem::Separator(Separator::default())];
        assert!(selectable_indices(&choices).is_empty());
    }

    // -- move_cursor --

    #[test]
    fn move_cursor_down_no_loop() {
        let indices = vec![0, 1, 2];
        assert_eq!(move_cursor(0, 1, &indices, false), 1);
        assert_eq!(move_cursor(1, 1, &indices, false), 2);
        // at end, clamp
        assert_eq!(move_cursor(2, 1, &indices, false), 2);
    }

    #[test]
    fn move_cursor_up_no_loop() {
        let indices = vec![0, 1, 2];
        assert_eq!(move_cursor(2, -1, &indices, false), 1);
        assert_eq!(move_cursor(1, -1, &indices, false), 0);
        // at start, clamp
        assert_eq!(move_cursor(0, -1, &indices, false), 0);
    }

    #[test]
    fn move_cursor_down_with_loop() {
        let indices = vec![0, 1, 2];
        assert_eq!(move_cursor(2, 1, &indices, true), 0);
    }

    #[test]
    fn move_cursor_up_with_loop() {
        let indices = vec![0, 1, 2];
        assert_eq!(move_cursor(0, -1, &indices, true), 2);
    }

    #[test]
    fn move_cursor_skips_gaps() {
        // Indices with gaps (separator at 1)
        let indices = vec![0, 2, 3];
        assert_eq!(move_cursor(0, 1, &indices, false), 2);
        assert_eq!(move_cursor(2, -1, &indices, false), 0);
    }

    #[test]
    fn move_cursor_single_item() {
        let indices = vec![0];
        assert_eq!(move_cursor(0, 1, &indices, true), 0);
        assert_eq!(move_cursor(0, -1, &indices, true), 0);
        assert_eq!(move_cursor(0, 1, &indices, false), 0);
        assert_eq!(move_cursor(0, -1, &indices, false), 0);
    }

    // -- render_items --

    #[test]
    fn render_items_basic() {
        let choices = make_choices(&["Alpha", "Beta", "Gamma"]);
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 10, t);
        assert_eq!(items.len(), 3);
        // First item is at cursor -> has pointer symbol
        assert!(items[0].1.contains(t.sym_pointer));
        assert!(items[0].1.contains("Alpha"));
        // Others are plain
        assert!(items[1].1.contains("Beta"));
        assert!(!items[1].1.contains(t.sym_pointer));
        assert!(items[2].1.contains("Gamma"));
    }

    #[test]
    fn render_items_with_separator() {
        let mut choices = make_choices(&["A"]);
        choices.insert(0, ChoiceItem::Separator(Separator::new("Section")));
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 1, 10, t);
        assert_eq!(items.len(), 2);
        assert!(items[0].1.contains("Section"));
        assert!(items[1].1.contains("A"));
    }

    #[test]
    fn render_items_disabled_shows_disabled_text() {
        let mut c = Choice::new("Premium", json!("premium"));
        c.disabled = Some(json!("Paid only"));
        let choices = vec![
            ChoiceItem::Choice(Choice::new("Free", json!("free"))),
            ChoiceItem::Choice(c),
        ];
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 10, t);
        assert_eq!(items.len(), 2);
        assert!(items[1].1.contains("disabled"));
        assert!(items[1].1.contains("Paid only"));
    }

    #[test]
    fn render_items_description_shown_at_cursor() {
        let mut c = Choice::new("Deploy", json!("deploy"));
        c.description = Some("Push to production".into());
        let choices = vec![ChoiceItem::Choice(c)];
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 10, t);
        assert!(
            items[0].1.contains("Push to production"),
            "Description should appear at cursor: {:?}",
            items[0].1
        );
    }

    #[test]
    fn render_items_description_newlines_stripped() {
        let mut c = Choice::new("Item", json!("item"));
        c.description = Some("line1\nline2\rline3".into());
        let choices = vec![ChoiceItem::Choice(c)];
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 10, t);
        // Should not contain raw newlines in the rendered text
        assert!(
            !items[0].1.contains('\n'),
            "Description newlines should be stripped"
        );
        assert!(
            !items[0].1.contains('\r'),
            "Description carriage returns should be stripped"
        );
        assert!(items[0].1.contains("line1line2line3"));
    }

    #[test]
    fn render_items_pagination() {
        let choices = make_choices(&["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]);
        let t = &DEFAULT_THEME;
        // page_size=3, cursor at middle
        let items = render_items(&choices, 5, 3, t);
        // Should show "(more above)" and "(more below)" plus 3 items = 5 total
        let texts: Vec<&str> = items.iter().map(|(_, t)| t.as_str()).collect();
        assert!(
            texts.iter().any(|t| t.contains("more above")),
            "Should show 'more above': {texts:?}"
        );
        assert!(
            texts.iter().any(|t| t.contains("more below")),
            "Should show 'more below': {texts:?}"
        );
    }

    #[test]
    fn render_items_first_page_no_more_above() {
        let choices = make_choices(&["A", "B", "C", "D", "E"]);
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 3, t);
        let texts: Vec<&str> = items.iter().map(|(_, t)| t.as_str()).collect();
        assert!(
            !texts.iter().any(|t| t.contains("more above")),
            "First page should not show 'more above': {texts:?}"
        );
    }

    #[test]
    fn render_items_last_page_no_more_below() {
        let choices = make_choices(&["A", "B", "C", "D", "E"]);
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 4, 3, t);
        let texts: Vec<&str> = items.iter().map(|(_, t)| t.as_str()).collect();
        assert!(
            !texts.iter().any(|t| t.contains("more below")),
            "Last page should not show 'more below': {texts:?}"
        );
    }

    #[test]
    fn render_items_page_size_larger_than_list() {
        let choices = make_choices(&["A", "B"]);
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 100, t);
        assert_eq!(items.len(), 2); // no pagination markers
    }

    #[test]
    fn render_items_cursor_style_uses_highlight_colour() {
        let choices = make_choices(&["X"]);
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 10, t);
        let highlight = ansi_color(t.highlight);
        assert_eq!(
            items[0].0, highlight,
            "Cursor item should use highlight colour"
        );
    }

    #[test]
    fn render_items_non_cursor_has_empty_style() {
        let choices = make_choices(&["A", "B"]);
        let t = &DEFAULT_THEME;
        let items = render_items(&choices, 0, 10, t);
        assert_eq!(items[1].0, "", "Non-cursor item should have empty style");
    }
}
