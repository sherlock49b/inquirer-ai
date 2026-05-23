use crate::agent::agent_prompt_with_retry;
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{format_error, format_question, format_success, read_line};
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
    let suffix = format!(" ({keys})");
    let prompt = format_question(&config.message, &suffix);
    loop {
        let raw = read_line(&prompt)?;
        let lower = raw.trim().to_lowercase();
        if lower == "h" || lower == "help" {
            for c in &config.choices {
                eprintln!("  {}) {}", c.key, c.name);
            }
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
