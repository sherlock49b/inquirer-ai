use crate::agent::agent_prompt_with_retry;
use crate::errors::Result;
use crate::mode::is_agent_mode;
use crate::terminal::{format_question, format_success, read_line};
use serde_json::{json, Value};

pub struct PathConfig {
    pub message: String,
    pub default: Option<String>,
    pub only_directories: bool,
}

impl PathConfig {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            default: None,
            only_directories: false,
        }
    }
}

pub fn path(config: PathConfig) -> Result<String> {
    if is_agent_mode() {
        path_agent(&config)
    } else {
        path_terminal(&config)
    }
}

fn path_agent(config: &PathConfig) -> Result<String> {
    let default = config.default.clone();
    let payload = json!({
        "type": "path",
        "message": config.message,
        "default": config.default,
        "only_directories": config.only_directories,
    });

    agent_prompt_with_retry(&payload, move |answer| match answer {
        Value::Null => Ok(default.clone().unwrap_or_default()),
        Value::String(s) => Ok(s),
        other => Ok(other.to_string()),
    })
}

fn path_terminal(config: &PathConfig) -> Result<String> {
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
