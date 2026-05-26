use crate::agent::agent_prompt_with_retry;
use crate::errors::Result;
use crate::mode::is_agent_mode;
use crate::terminal::{format_question, format_success, read_line, read_line_with_default};
use serde_json::{json, Value};

pub type Validator = Box<dyn Fn(&str) -> std::result::Result<(), String>>;

pub struct TextConfig {
    pub message: String,
    pub default: Option<String>,
    pub validate: Option<Validator>,
    pub filter: Option<Box<dyn Fn(String) -> String>>,
    pub keep_input: bool,
}

impl TextConfig {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            default: None,
            validate: None,
            filter: None,
            keep_input: true,
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
        if let Some(v) = &config.validate {
            if let Err(msg) = v(&result) {
                return Err(crate::errors::InquirerError::Validation(msg));
            }
        }
        if let Some(f) = &config.filter {
            result = f(result);
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
    let mut prefill: Option<String> = None;
    loop {
        let prompt = format_question(&config.message, &suffix);
        let raw = if config.keep_input {
            read_line_with_default(&prompt, prefill.as_deref())?
        } else {
            read_line(&prompt)?
        };
        let mut result = if raw.is_empty() {
            config.default.clone().unwrap_or_default()
        } else {
            raw.clone()
        };
        if let Some(v) = &config.validate {
            use std::panic::{catch_unwind, AssertUnwindSafe};
            let res_ref = &result;
            match catch_unwind(AssertUnwindSafe(|| v(res_ref))) {
                Ok(Ok(())) => {}
                Ok(Err(msg)) => {
                    eprintln!("{}", crate::terminal::format_error(&msg));
                    if config.keep_input {
                        prefill = Some(raw);
                    }
                    continue;
                }
                Err(panic_payload) => {
                    let msg = if let Some(s) = panic_payload.downcast_ref::<&str>() {
                        format!("Validator panicked: {s}")
                    } else if let Some(s) = panic_payload.downcast_ref::<String>() {
                        format!("Validator panicked: {s}")
                    } else {
                        "Validator panicked with an unknown payload".to_string()
                    };
                    return Err(crate::errors::InquirerError::Validation(msg));
                }
            }
        }
        if let Some(f) = &config.filter {
            result = f(result);
        }
        eprintln!("{}", format_success(&config.message, &result));
        return Ok(result);
    }
}
