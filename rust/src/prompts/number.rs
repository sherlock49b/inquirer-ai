use crate::agent::agent_prompt_with_retry;
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::{
    format_error, format_question, format_success, read_line, read_line_with_default,
};
use serde_json::{json, Value};

pub struct NumberConfig {
    pub message: String,
    pub default: Option<f64>,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub step: Option<f64>,
    pub float_allowed: bool,
    pub keep_input: bool,
}

impl NumberConfig {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            default: None,
            min: None,
            max: None,
            step: None,
            float_allowed: true,
            keep_input: true,
        }
    }
}

pub fn number(config: NumberConfig) -> Result<f64> {
    if is_agent_mode() {
        number_agent(&config)
    } else {
        number_terminal(&config)
    }
}

/// Returns true iff `s` fully matches the numeric-string grammar (R2):
/// `^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$`
/// (optional sign; required integer part; optional `.fraction`; optional
/// exponent). Rejects "1_000", "3abc", "0x10", ".5", "5.", "", "+".
fn matches_number_grammar(s: &str) -> bool {
    let bytes = s.as_bytes();
    let mut i = 0;
    let n = bytes.len();

    // optional sign
    if i < n && (bytes[i] == b'+' || bytes[i] == b'-') {
        i += 1;
    }

    // required integer part: one or more ASCII digits
    let int_start = i;
    while i < n && bytes[i].is_ascii_digit() {
        i += 1;
    }
    if i == int_start {
        return false;
    }

    // optional fraction: '.' followed by one or more digits
    if i < n && bytes[i] == b'.' {
        i += 1;
        let frac_start = i;
        while i < n && bytes[i].is_ascii_digit() {
            i += 1;
        }
        if i == frac_start {
            return false; // "5." not allowed
        }
    }

    // optional exponent: [eE] [+-]? digits+
    if i < n && (bytes[i] == b'e' || bytes[i] == b'E') {
        i += 1;
        if i < n && (bytes[i] == b'+' || bytes[i] == b'-') {
            i += 1;
        }
        let exp_start = i;
        while i < n && bytes[i].is_ascii_digit() {
            i += 1;
        }
        if i == exp_start {
            return false;
        }
    }

    i == n
}

pub fn validate_number(value: &Value, config: &NumberConfig) -> Result<f64> {
    let num = match value {
        Value::Null => {
            return config
                .default
                .ok_or_else(|| InquirerError::Validation("Expected a number, got null".into()));
        }
        Value::Number(n) => n
            .as_f64()
            .ok_or_else(|| InquirerError::Validation("Not a valid number".into()))?,
        Value::String(s) => {
            // Trim leading/trailing ASCII whitespace, then require the
            // remainder to fully match the numeric grammar (R2) before parsing.
            let trimmed = s.trim_matches(|c: char| c.is_ascii_whitespace());
            if !matches_number_grammar(trimmed) {
                return Err(InquirerError::Validation(format!(
                    "Not a valid number: {s:?}"
                )));
            }
            trimmed
                .parse::<f64>()
                .map_err(|_| InquirerError::Validation(format!("Not a valid number: {s:?}")))?
        }
        Value::Bool(_) => {
            return Err(InquirerError::Validation(
                "Expected a number, got boolean".into(),
            ))
        }
        _ => {
            return Err(InquirerError::Validation(format!(
                "Expected a number, got {value}"
            )))
        }
    };

    if num.is_nan() || num.is_infinite() {
        return Err(InquirerError::Validation(format!(
            "Not a valid number: {value}"
        )));
    }

    if !config.float_allowed && num.fract() != 0.0 {
        return Err(InquirerError::Validation(
            "Decimal numbers are not allowed".into(),
        ));
    }

    let num = if !config.float_allowed {
        num.trunc()
    } else {
        num
    };

    if let Some(min) = config.min {
        if num < min {
            return Err(InquirerError::Validation(format!("Must be at least {min}")));
        }
    }
    if let Some(max) = config.max {
        if num > max {
            return Err(InquirerError::Validation(format!("Must be at most {max}")));
        }
    }

    if let Some(step) = config.step {
        let base = config.min.unwrap_or(0.0);
        let remainder = (num - base) % step;
        if remainder.abs() > 1e-9 && (remainder - step).abs() > 1e-9 {
            return Err(InquirerError::Validation(format!(
                "Must be a multiple of {step} (from {base})"
            )));
        }
    }

    Ok(num)
}

fn number_agent(config: &NumberConfig) -> Result<f64> {
    let payload = json!({
        "type": "number",
        "message": config.message,
        "default": config.default,
        "min": config.min,
        "max": config.max,
        "num_step": config.step,
        "float_allowed": config.float_allowed,
    });

    agent_prompt_with_retry(&payload, |answer| validate_number(&answer, config))
}

fn number_terminal(config: &NumberConfig) -> Result<f64> {
    let suffix = config
        .default
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
        if raw.is_empty() {
            if let Some(d) = config.default {
                eprintln!("{}", format_success(&config.message, &d.to_string()));
                return Ok(d);
            }
        }
        let value = Value::String(raw.clone());
        match validate_number(&value, config) {
            Ok(n) => {
                eprintln!("{}", format_success(&config.message, &n.to_string()));
                return Ok(n);
            }
            Err(InquirerError::Validation(msg)) => {
                eprintln!("{}", format_error(&msg));
                if config.keep_input {
                    prefill = Some(raw);
                }
            }
            Err(e) => return Err(e),
        }
    }
}
