use crate::agent::{agent_receive, agent_send};
use crate::choice::{Choice, ChoiceItem};
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{format_error, format_question, format_success, read_line};
use serde_json::{json, Value};

pub struct RawlistConfig {
    pub message: String,
    pub choices: Vec<Choice>,
}

impl RawlistConfig {
    pub fn new(message: impl Into<String>, choices: Vec<ChoiceItem>) -> Self {
        let choices: Vec<Choice> = choices
            .into_iter()
            .filter_map(|c| match c {
                ChoiceItem::Choice(c) => Some(c),
                _ => None,
            })
            .collect();
        Self {
            message: message.into(),
            choices,
        }
    }
}

pub fn rawlist(config: RawlistConfig) -> Result<Value> {
    if config.choices.is_empty() {
        return Err(InquirerError::InvalidChoice(
            "choices cannot be empty".into(),
        ));
    }

    if is_agent_mode() {
        rawlist_agent(&config)
    } else {
        rawlist_terminal(&config)
    }
}

pub fn validate_rawlist(value: &Value, choices: &[Choice]) -> Result<Value> {
    if let Some(idx) = value.as_u64() {
        let idx = idx as usize;
        if idx >= 1 && idx <= choices.len() {
            return Ok(choices[idx - 1].value.clone());
        }
    }

    for c in choices {
        if *value == c.value || value.as_str() == Some(&c.name) {
            return Ok(c.value.clone());
        }
    }

    Err(InquirerError::Validation(format!(
        "Invalid choice: {value}"
    )))
}

fn rawlist_agent(config: &RawlistConfig) -> Result<Value> {
    let choices_json: Vec<Value> = config
        .choices
        .iter()
        .map(|c| serde_json::to_value(c).unwrap_or(Value::Null))
        .collect();
    let payload = json!({
        "type": "rawlist",
        "message": config.message,
        "default": null,
        "choices": choices_json,
    });
    agent_send(&payload)?;
    let answer = agent_receive()?;
    validate_rawlist(&answer, &config.choices)
}

fn rawlist_terminal(config: &RawlistConfig) -> Result<Value> {
    for (i, c) in config.choices.iter().enumerate() {
        eprintln!("  {}) {}", i + 1, c.name);
    }
    let prompt = format_question(&config.message, "");
    loop {
        let raw = read_line(&prompt)?;
        if let Ok(idx) = raw.parse::<usize>() {
            if idx >= 1 && idx <= config.choices.len() {
                let c = &config.choices[idx - 1];
                let display = c.short.as_deref().unwrap_or(&c.name);
                eprintln!("{}", format_success(&config.message, display));
                return Ok(c.value.clone());
            }
        }
        eprintln!(
            "{}",
            format_error(&format!(
                "Please enter a number between 1 and {}",
                config.choices.len()
            ))
        );
    }
}
