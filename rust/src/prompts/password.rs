use crate::agent::agent_prompt_with_retry;
use crate::errors::Result;
use crate::mode::is_agent_mode;
use crate::terminal::{format_question, format_success, read_line};
use serde_json::{json, Value};

pub struct PasswordConfig {
    pub message: String,
    pub mask: Option<String>,
}

impl PasswordConfig {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            mask: Some("*".to_string()),
        }
    }
}

pub fn password(config: PasswordConfig) -> Result<String> {
    if is_agent_mode() {
        password_agent(&config)
    } else {
        password_terminal(&config)
    }
}

fn password_agent(config: &PasswordConfig) -> Result<String> {
    let payload = json!({
        "type": "password",
        "message": config.message,
        "default": null,
        "mask": config.mask,
    });

    agent_prompt_with_retry(&payload, |answer| match answer {
        Value::Null => Ok(String::new()),
        Value::String(s) => Ok(s),
        other => Ok(other.to_string()),
    })
}

fn password_terminal(config: &PasswordConfig) -> Result<String> {
    let prompt = format_question(&config.message, "");
    let result = read_line(&prompt)?;
    let display = match &config.mask {
        Some(m) => m.repeat(result.len()),
        None => "****".to_string(),
    };
    eprintln!("{}", format_success(&config.message, &display));
    Ok(result)
}
