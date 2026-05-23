use crate::agent::agent_prompt_with_retry;
use crate::errors::Result;
use crate::mode::is_agent_mode;
use crate::terminal::{format_question, format_success, read_line};
use serde_json::{json, Value};

pub type Validator = Box<dyn Fn(&str) -> std::result::Result<(), String>>;

pub struct TextConfig {
    pub message: String,
    pub default: Option<String>,
    pub validate: Option<Validator>,
    pub filter: Option<Box<dyn Fn(String) -> String>>,
}

impl TextConfig {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            default: None,
            validate: None,
            filter: None,
        }
    }
}

pub fn text(config: TextConfig) -> Result<String> {
    if is_agent_mode() {
        text_agent(&config)
    } else {
        text_terminal(&config)
    }
}

fn validate_answer(value: &Value, default: &Option<String>) -> String {
    match value {
        Value::Null => default.clone().unwrap_or_default(),
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

fn text_agent(config: &TextConfig) -> Result<String> {
    let payload = json!({
        "type": "input",
        "message": config.message,
        "default": config.default,
    });

    agent_prompt_with_retry(&payload, |answer| {
        let mut result = validate_answer(&answer, &config.default);
        if let Some(f) = &config.filter {
            result = f(result);
        }
        if let Some(v) = &config.validate {
            if let Err(msg) = v(&result) {
                return Err(crate::errors::InquirerError::Validation(msg));
            }
        }
        Ok(result)
    })
}

fn text_terminal(config: &TextConfig) -> Result<String> {
    let suffix = config
        .default
        .as_ref()
        .map(|d| format!(" ({d})"))
        .unwrap_or_default();
    loop {
        let prompt = format_question(&config.message, &suffix);
        let raw = read_line(&prompt)?;
        let mut result = if raw.is_empty() {
            config.default.clone().unwrap_or_default()
        } else {
            raw
        };
        if let Some(f) = &config.filter {
            result = f(result);
        }
        if let Some(v) = &config.validate {
            if let Err(msg) = v(&result) {
                eprintln!("{}", crate::terminal::format_error(&msg));
                continue;
            }
        }
        eprintln!("{}", format_success(&config.message, &result));
        return Ok(result);
    }
}
