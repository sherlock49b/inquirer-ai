use crate::errors::{InquirerError, Result};
use serde_json::Value;
use std::io::{self, BufRead, Write};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Once;

static HANDSHAKE: Once = Once::new();
static STEP: AtomicUsize = AtomicUsize::new(0);
const VERSION: &str = "0.2.0";

// ---------------------------------------------------------------------------
// fd-based I/O helpers
// ---------------------------------------------------------------------------

/// Creates a File from a raw fd specified in an environment variable.
///
/// # Safety
///
/// The fd must be valid and open. The caller must ensure the fd
/// is not closed elsewhere while the File is in use.
#[cfg(unix)]
fn file_from_env_fd(var: &str) -> Option<std::fs::File> {
    use std::os::unix::io::FromRawFd;
    std::env::var(var)
        .ok()
        .and_then(|s| s.parse::<i32>().ok())
        .map(|fd| unsafe { std::fs::File::from_raw_fd(fd) })
}

#[cfg(not(unix))]
fn file_from_env_fd(_var: &str) -> Option<std::fs::File> {
    None
}

fn fd_out_file() -> Option<std::fs::File> {
    file_from_env_fd("INQUIRER_AI_FD_OUT")
}

fn fd_in_file() -> Option<std::fs::File> {
    file_from_env_fd("INQUIRER_AI_FD_IN")
}

/// Write a single JSON line to the agent output channel.
fn write_line(line: &str) -> Result<()> {
    if let Some(mut f) = fd_out_file() {
        writeln!(f, "{line}")?;
        f.flush()?;
    } else {
        let mut stdout = io::stdout().lock();
        writeln!(stdout, "{line}")?;
        stdout.flush()?;
    }
    Ok(())
}

/// Read a single line from the agent input channel.
fn read_input_line() -> Result<String> {
    let mut line = String::new();
    let bytes = if let Some(f) = fd_in_file() {
        let mut reader = io::BufReader::new(f);
        reader.read_line(&mut line)?
    } else {
        let stdin = io::stdin();
        stdin.lock().read_line(&mut line)?
    };
    if bytes == 0 {
        return Err(InquirerError::PromptAborted(
            "No response received (input closed). Expected JSON like: {\"answer\": \"<value>\"}"
                .to_string(),
        ));
    }
    Ok(line)
}

// ---------------------------------------------------------------------------
// Handshake
// ---------------------------------------------------------------------------

fn send_handshake() {
    HANDSHAKE.call_once(|| {
        let meta = serde_json::json!({
            "kind": "handshake",
            "protocol": "inquirer-ai",
            "version": VERSION,
            "format": "jsonl",
            "total": null,
            "interaction": "sequential",
            "description": concat!(
                "Interactive prompt protocol. Prompts are sent one at a time — ",
                "read one JSON line from stdout, respond with one JSON line on stdin, ",
                "then wait for the next prompt. Do NOT send all answers at once. ",
                "Use a named pipe (mkfifo) or line-buffered I/O for bidirectional communication."
            ),
            "example_response": {"answer": "<value>"}
        });
        let _ = write_line(&meta.to_string());
    });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

pub fn agent_send(payload: &Value) -> Result<()> {
    send_handshake();
    let step = STEP.fetch_add(1, Ordering::SeqCst) + 1;

    // Merge kind, step, total into the payload
    let mut obj = match payload {
        Value::Object(map) => map.clone(),
        _ => serde_json::Map::new(),
    };
    obj.insert("kind".to_string(), Value::String("prompt".to_string()));
    obj.insert("step".to_string(), Value::Number(step.into()));
    obj.insert("total".to_string(), Value::Null);

    let out = Value::Object(obj);
    write_line(&out.to_string())
}

pub fn agent_receive() -> Result<Value> {
    loop {
        let line = read_input_line()?;

        let resp: Value = serde_json::from_str(line.trim()).map_err(|e| {
            InquirerError::Validation(format!(
                "Invalid JSON response: {e}. Expected JSON like: {{\"answer\": \"<value>\"}}"
            ))
        })?;

        if resp.get("kind").and_then(|v| v.as_str()) == Some("handshake_ack") {
            continue;
        }

        return extract_answer(&resp);
    }
}

pub fn extract_answer(resp: &Value) -> Result<Value> {
    match resp.get("answer") {
        Some(answer) => Ok(answer.clone()),
        None => Err(InquirerError::Validation(
            "Response must be a JSON object with an \"answer\" key".to_string(),
        )),
    }
}

pub fn agent_send_validation_error(msg: &str) -> Result<()> {
    let payload = serde_json::json!({
        "kind": "validation_error",
        "message": msg,
    });
    write_line(&payload.to_string())
}

pub fn agent_send_error(msg: &str) -> Result<()> {
    let payload = serde_json::json!({
        "kind": "error",
        "message": msg,
    });
    write_line(&payload.to_string())
}

/// Send a prompt payload to the agent, receive a response, validate it, and
/// retry up to 3 times on validation errors.
pub fn agent_prompt_with_retry<T>(
    payload: &Value,
    validate: impl Fn(Value) -> Result<T>,
) -> Result<T> {
    const MAX_RETRIES: usize = 3;
    for attempt in 0..MAX_RETRIES {
        agent_send(payload)?;
        let answer = agent_receive()?;
        match validate(answer) {
            Ok(val) => return Ok(val),
            Err(InquirerError::Validation(msg)) => {
                if attempt + 1 < MAX_RETRIES {
                    agent_send_validation_error(&msg)?;
                    continue;
                }
                return Err(InquirerError::Validation(msg));
            }
            Err(e) => return Err(e),
        }
    }
    unreachable!()
}

#[cfg(test)]
pub fn reset_handshake() {
    // SAFETY: Only used in tests. Since Once is not resettable in std,
    // tests that need multiple handshakes should use separate processes.
    // For unit tests, we accept that handshake is sent only once.
}
