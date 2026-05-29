use crate::agent::agent_prompt_with_retry;
use crate::errors::{InquirerError, Result};
use crate::mode::is_agent_mode;
use crate::terminal::format_success;
use serde_json::{json, Value};
use std::io::{Read, Write};
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
    let default = config.default.clone();
    let payload = json!({
        "type": "editor",
        "message": config.message,
        "default": config.default,
        "postfix": config.postfix,
    });

    agent_prompt_with_retry(&payload, move |answer| match answer {
        Value::Null => Ok(default.clone().unwrap_or_default()),
        Value::String(s) => Ok(s),
        other => Ok(other.to_string()),
    })
}

fn editor_terminal(config: &EditorConfig) -> Result<String> {
    let editor_cmd = std::env::var("VISUAL")
        .or_else(|_| std::env::var("EDITOR"))
        .unwrap_or_else(|_| "vi".to_string());

    // Quote-aware shell-word split, then exec WITHOUT a shell (no injection).
    let parts = shell_words::split(&editor_cmd)
        .map_err(|e| InquirerError::Editor(format!("Invalid $EDITOR/$VISUAL: {e}")))?;
    let (cmd, args) = parts
        .split_first()
        .ok_or_else(|| InquirerError::Editor("Empty EDITOR command".into()))?;

    // Secure temp file: randomized name, mode 0600, created with O_EXCL (no
    // symlink follow, no clobber), removed on EVERY exit path via Drop.
    let mut named = build_temp_file(&config.postfix)?;

    if let Some(d) = &config.default {
        named
            .as_file_mut()
            .write_all(d.as_bytes())
            .map_err(InquirerError::Io)?;
        named.as_file_mut().flush().map_err(InquirerError::Io)?;
    }

    let status = Command::new(cmd)
        .args(args)
        .arg(named.path())
        .status()
        .map_err(|_| {
            InquirerError::Editor(format!(
                "Editor not found: {editor_cmd:?}. Set $VISUAL or $EDITOR."
            ))
        })?;

    if !status.success() {
        // `named` is dropped here, removing the temp file.
        return Err(InquirerError::Editor(format!(
            "Editor exited with code {}",
            status.code().unwrap_or(-1)
        )));
    }

    // Re-read from the start: the editor may have rewritten the file.
    let mut content = String::new();
    {
        let mut f = std::fs::File::open(named.path()).map_err(InquirerError::Io)?;
        f.read_to_string(&mut content).map_err(InquirerError::Io)?;
    }
    // `named` is dropped at end of scope, removing the temp file on success too.

    eprintln!("{}", format_success(&config.message, "(editor)"));
    Ok(content)
}

/// Create a secure temporary file with a randomized name, mode 0600, created
/// with O_EXCL (no clobber, no symlink follow), using the configured postfix
/// as the file suffix.
fn build_temp_file(postfix: &str) -> Result<tempfile::NamedTempFile> {
    let mut builder = tempfile::Builder::new();
    builder.prefix("inquirer-edit-").suffix(postfix);
    let named = builder
        .tempfile()
        .map_err(|e| InquirerError::Editor(format!("Failed to create temp file: {e}")))?;
    // tempfile creates with O_EXCL and 0600 on unix; set the mode explicitly
    // to be robust against umask differences.
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        named
            .as_file()
            .set_permissions(std::fs::Permissions::from_mode(0o600))
            .map_err(InquirerError::Io)?;
    }
    Ok(named)
}
