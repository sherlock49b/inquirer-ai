use crate::agent::agent_prompt_with_retry;
use crate::errors::Result;
use crate::mode::is_agent_mode;
use crate::terminal::{format_error, format_question, format_success, read_line};
use serde_json::{json, Value};

pub struct ConfirmConfig {
    pub message: String,
    pub default: bool,
}

impl ConfirmConfig {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            default: false,
        }
    }
}

pub fn confirm(config: ConfirmConfig) -> Result<bool> {
    if is_agent_mode() {
        confirm_agent(&config)
    } else {
        confirm_terminal(&config)
    }
}

pub fn coerce_bool(value: &Value) -> bool {
    match value {
        Value::Bool(b) => *b,
        Value::String(s) => matches!(s.to_lowercase().as_str(), "y" | "yes" | "true" | "1"),
        Value::Number(n) => n.as_f64().unwrap_or(0.0) != 0.0,
        Value::Null => false,
        _ => false,
    }
}

fn confirm_agent(config: &ConfirmConfig) -> Result<bool> {
    let payload = json!({
        "type": "confirm",
        "message": config.message,
        "default": config.default,
    });

    let default = config.default;
    agent_prompt_with_retry(&payload, move |answer| match answer {
        // A null answer falls back to the prompt default (R5).
        Value::Null => Ok(default),
        other => Ok(coerce_bool(&other)),
    })
}

fn confirm_terminal(config: &ConfirmConfig) -> Result<bool> {
    let hint = if config.default { "Y/n" } else { "y/N" };
    let suffix = format!(" ({hint})");
    loop {
        let prompt = format_question(&config.message, &suffix);
        let raw = read_line(&prompt)?;
        if raw.is_empty() {
            eprintln!(
                "{}",
                format_success(&config.message, if config.default { "Yes" } else { "No" })
            );
            return Ok(config.default);
        }
        match raw.trim().to_lowercase().as_str() {
            "y" | "yes" => {
                eprintln!("{}", format_success(&config.message, "Yes"));
                return Ok(true);
            }
            "n" | "no" => {
                eprintln!("{}", format_success(&config.message, "No"));
                return Ok(false);
            }
            _ => {
                eprintln!("{}", format_error("Invalid input. Please enter y or n."));
            }
        }
    }
}
