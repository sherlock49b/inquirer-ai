use crate::agent::agent_prompt_with_retry;
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
        // The selectable list excludes separators AND disabled choices; only
        // these are numbered/advertised and matchable (R5/R6).
        let choices: Vec<Choice> = choices
            .into_iter()
            .filter_map(|c| match c {
                ChoiceItem::Choice(c) if !c.is_disabled() => Some(c),
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
    // 1-based integer index over the selectable list. A JSON number is treated
    // as an index ONLY if it is an integer; non-integer numbers (e.g. 1.5) are
    // rejected rather than matched as a value.
    if let Value::Number(n) = value {
        match integer_index(n) {
            Some(idx) if idx >= 1 && idx <= choices.len() => {
                return Ok(choices[idx - 1].value.clone());
            }
            // Numeric but out of range or non-integer: fall through to value
            // matching (a number could still equal a choice value).
            _ => {}
        }
    }

    for c in choices {
        if *value == c.value || value.as_str() == Some(&c.name) {
            return Ok(c.value.clone());
        }
    }

    let valid = choices.iter().map(|c| &c.value);
    Err(InquirerError::Validation(
        crate::prompts::invalid_choice_message(value, valid),
    ))
}

/// Interpret a JSON number as a 1-based index, returning `Some(idx)` only when
/// it is a non-negative integer value.
fn integer_index(n: &serde_json::Number) -> Option<usize> {
    if let Some(u) = n.as_u64() {
        return usize::try_from(u).ok();
    }
    // Integer-valued float (e.g. 2.0) counts; 1.5 does not.
    if let Some(f) = n.as_f64() {
        if f.fract() == 0.0 && f >= 0.0 {
            return Some(f as usize);
        }
    }
    None
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

    agent_prompt_with_retry(&payload, |answer| {
        validate_rawlist(&answer, &config.choices)
    })
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
