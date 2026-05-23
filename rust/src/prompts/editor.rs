use crate::agent::{agent_receive, agent_send};
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::format_success;
use serde_json::{json, Value};
use std::fs;
use std::process::Command;

pub struct EditorConfig {
    pub message: String,
    pub default: Option<String>,
    pub postfix: String,
}

impl EditorConfig {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            default: None,
            postfix: ".txt".to_string(),
        }
    }
}

pub fn editor(config: EditorConfig) -> Result<String> {
    if is_agent_mode() {
        editor_agent(&config)
    } else {
        editor_terminal(&config)
    }
}

fn editor_agent(config: &EditorConfig) -> Result<String> {
    let payload = json!({
        "type": "editor",
        "message": config.message,
        "default": config.default,
        "postfix": config.postfix,
    });
    agent_send(&payload)?;
    let answer = agent_receive()?;
    match answer {
        Value::Null => Ok(config.default.clone().unwrap_or_default()),
        Value::String(s) => Ok(s),
        other => Ok(other.to_string()),
    }
}

fn editor_terminal(config: &EditorConfig) -> Result<String> {
    let editor_cmd = std::env::var("VISUAL")
        .or_else(|_| std::env::var("EDITOR"))
        .unwrap_or_else(|_| "vi".to_string());

    let dir = std::env::temp_dir();
    let tmp_path = dir.join(format!("inquirer-edit{}", config.postfix));

    if let Some(d) = &config.default {
        fs::write(&tmp_path, d)?;
    } else {
        fs::write(&tmp_path, "")?;
    }

    let parts: Vec<&str> = editor_cmd.split_whitespace().collect();
    let (cmd, args) = parts
        .split_first()
        .ok_or_else(|| InquirerError::Editor("Empty EDITOR command".into()))?;

    let status = Command::new(cmd)
        .args(args)
        .arg(&tmp_path)
        .status()
        .map_err(|_| {
            InquirerError::Editor(format!(
                "Editor not found: {editor_cmd:?}. Set $VISUAL or $EDITOR."
            ))
        })?;

    if !status.success() {
        let _ = fs::remove_file(&tmp_path);
        return Err(InquirerError::Editor(format!(
            "Editor exited with code {}",
            status.code().unwrap_or(-1)
        )));
    }

    let content = fs::read_to_string(&tmp_path)?;
    let _ = fs::remove_file(&tmp_path);

    eprintln!("{}", format_success(&config.message, "(editor)"));
    Ok(content)
}
