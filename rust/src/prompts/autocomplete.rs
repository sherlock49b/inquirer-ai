use crate::agent::agent_prompt_with_retry;
use crate::errors::Result;
use crate::mode::is_agent_mode;
use crate::terminal::{format_question, format_success, read_line};
use serde_json::{json, Value};

pub struct AutocompleteConfig {
    pub message: String,
    pub choices: Vec<String>,
    pub default: Option<String>,
}

impl AutocompleteConfig {
    pub fn new(message: impl Into<String>, choices: Vec<String>) -> Self {
        Self {
            message: message.into(),
            choices,
            default: None,
        }
    }
}

pub fn autocomplete(config: AutocompleteConfig) -> Result<String> {
    if is_agent_mode() {
        autocomplete_agent(&config)
    } else {
        autocomplete_terminal(&config)
    }
}

fn autocomplete_agent(config: &AutocompleteConfig) -> Result<String> {
    let default = config.default.clone();
    let payload = json!({
        "type": "autocomplete",
        "message": config.message,
        "default": config.default,
        "choices": config.choices,
    });

    agent_prompt_with_retry(&payload, move |answer| match answer {
        Value::Null => Ok(default.clone().unwrap_or_default()),
        Value::String(s) => Ok(s),
        other => Ok(other.to_string()),
    })
}

fn autocomplete_terminal(config: &AutocompleteConfig) -> Result<String> {
    let suffix = config
        .default
        .as_ref()
        .map(|d| format!(" ({d})"))
        .unwrap_or_default();
    let prompt = format_question(&config.message, &suffix);
    let raw = read_line(&prompt)?;
    let result = if raw.is_empty() {
        config.default.clone().unwrap_or_default()
    } else {
        raw
    };
    eprintln!("{}", format_success(&config.message, &result));
    Ok(result)
}
