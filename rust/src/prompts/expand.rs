use crate::agent::agent_prompt_with_retry;
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{
    format_error, format_question, format_success, read_line, KeyInput, ListRenderer,
};
use crate::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use serde_json::{json, Value};

#[derive(Debug, Clone)]
pub struct ExpandChoice {
    pub key: String,
    pub name: String,
    pub value: Value,
}

pub struct ExpandConfig {
    pub message: String,
    pub choices: Vec<ExpandChoice>,
}

impl ExpandConfig {
    pub fn new(message: impl Into<String>, choices: Vec<ExpandChoice>) -> Self {
        Self {
            message: message.into(),
            choices,
        }
    }
}

pub fn expand(config: ExpandConfig) -> Result<Value> {
    if config.choices.is_empty() {
        return Err(InquirerError::InvalidChoice(
            "choices cannot be empty".into(),
        ));
    }

    let mut seen = std::collections::HashSet::new();
    for c in &config.choices {
        if !seen.insert(&c.key) {
            return Err(InquirerError::InvalidChoice(format!(
                "Duplicate expand key: {}",
                c.key
            )));
        }
    }

    if is_agent_mode() {
        expand_agent(&config)
    } else {
        expand_terminal(&config)
    }
}

pub fn validate_expand(value: &Value, choices: &[ExpandChoice]) -> Result<Value> {
    if let Some(s) = value.as_str() {
        let lower = s.to_lowercase();
        for c in choices {
            if lower == c.key || s == c.value.as_str().unwrap_or("") || s == c.name {
                return Ok(c.value.clone());
            }
        }
    }
    Err(InquirerError::Validation(format!(
        "Invalid choice: {value}"
    )))
}

fn expand_agent(config: &ExpandConfig) -> Result<Value> {
    let choices_json: Vec<Value> = config
        .choices
        .iter()
        .map(|c| {
            json!({
                "key": c.key,
                "name": c.name,
                "value": c.value,
            })
        })
        .collect();
    let payload = json!({
        "type": "expand",
        "message": config.message,
        "default": null,
        "choices": choices_json,
    });

    agent_prompt_with_retry(&payload, |answer| validate_expand(&answer, &config.choices))
}

fn expand_terminal(config: &ExpandConfig) -> Result<Value> {
    let keys: String = config
        .choices
        .iter()
        .map(|c| c.key.as_str())
        .collect::<Vec<_>>()
        .join("/");
    let compact_suffix = format!(" ({keys}/h)");
    let mut show_help = false;

    loop {
        if show_help {
            // Full menu mode using ListRenderer (raw mode)
            let t = &DEFAULT_THEME;
            ListRenderer::enable_raw()?;
            let mut renderer = ListRenderer::new();

            let mut cursor: usize = 0;

            loop {
                let header = format!(
                    "{}{}{}  {BOLD}{}{RESET}  (h: hide help)",
                    ansi_color(t.question),
                    t.sym_question,
                    RESET,
                    config.message,
                );
                let items: Vec<(String, String)> = config
                    .choices
                    .iter()
                    .enumerate()
                    .map(|(i, c)| {
                        if i == cursor {
                            let hc = ansi_color(t.highlight);
                            (hc, format!("{} {}) {}", t.sym_pointer, c.key, c.name))
                        } else {
                            (String::new(), format!("  {}) {}", c.key, c.name))
                        }
                    })
                    .collect();
                renderer.render(&header, &items);

                match crate::terminal::read_key()? {
                    KeyInput::Up | KeyInput::Char('k') => {
                        if cursor > 0 {
                            cursor -= 1;
                        } else {
                            cursor = config.choices.len() - 1;
                        }
                    }
                    KeyInput::Down | KeyInput::Char('j') => {
                        if cursor < config.choices.len() - 1 {
                            cursor += 1;
                        } else {
                            cursor = 0;
                        }
                    }
                    KeyInput::Enter => {
                        renderer.clear();
                        ListRenderer::disable_raw()?;
                        let c = &config.choices[cursor];
                        eprintln!("{}", format_success(&config.message, &c.name));
                        return Ok(c.value.clone());
                    }
                    KeyInput::Char('h') => {
                        renderer.clear();
                        ListRenderer::disable_raw()?;
                        show_help = false;
                        break;
                    }
                    KeyInput::Char(ch) => {
                        let lower = ch.to_ascii_lowercase();
                        let found = config.choices.iter().position(|c| {
                            c.key.len() == 1
                                && c.key.chars().next().unwrap().to_ascii_lowercase() == lower
                        });
                        if let Some(idx) = found {
                            renderer.clear();
                            ListRenderer::disable_raw()?;
                            let c = &config.choices[idx];
                            eprintln!("{}", format_success(&config.message, &c.name));
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
        } else {
            // Compact mode: simple line input
            let prompt = format_question(&config.message, &compact_suffix);
            let raw = read_line(&prompt)?;
            let lower = raw.trim().to_lowercase();
            if lower == "h" || lower == "help" {
                show_help = true;
                continue;
            }
            for c in &config.choices {
                if lower == c.key {
                    eprintln!("{}", format_success(&config.message, &c.name));
                    return Ok(c.value.clone());
                }
            }
            eprintln!("{}", format_error("Invalid key. Press h for help."));
        }
    }
}
