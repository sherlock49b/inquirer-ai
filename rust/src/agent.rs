use crate::errors::{InquirerError, Result};
use serde_json::Value;
use std::io::{self, BufRead, Write};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Once;

static HANDSHAKE: Once = Once::new();
static STEP: AtomicUsize = AtomicUsize::new(0);
const VERSION: &str = "0.2.1";

// ---------------------------------------------------------------------------
// fd-based I/O helpers
// ---------------------------------------------------------------------------

/// Creates a File from a raw fd specified in an environment variable.
///
/// Validates that the fd is actually open before constructing the File.
/// Returns `None` if the env var is missing, not a valid integer, or
/// points to a closed/invalid file descriptor.
#[cfg(unix)]
fn file_from_env_fd(var: &str) -> Option<std::fs::File> {
    use std::os::unix::io::FromRawFd;
    let fd: i32 = std::env::var(var).ok()?.parse().ok()?;

    // Validate the fd is open using fcntl(fd, F_GETFD).
    // Returns -1 if the fd is not open.
    if unsafe { libc::fcntl(fd, libc::F_GETFD) } == -1 {
        return None;
    }

    // SAFETY: We verified the fd is open above.
    Some(unsafe { std::fs::File::from_raw_fd(fd) })
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
///
/// If the `validate` closure panics, the panic is caught and converted into
/// an `InquirerError::Validation` so that the caller never observes UB from
/// an unwinding validator.
pub fn agent_prompt_with_retry<T>(
    payload: &Value,
    validate: impl Fn(Value) -> Result<T>,
) -> Result<T> {
    use std::panic::{catch_unwind, AssertUnwindSafe};

    const MAX_RETRIES: usize = 3;
    for attempt in 0..MAX_RETRIES {
        agent_send(payload)?;
        let answer = agent_receive()?;

        let result = catch_unwind(AssertUnwindSafe(|| validate(answer)));

        match result {
            Ok(Ok(val)) => return Ok(val),
            Ok(Err(InquirerError::Validation(msg))) => {
                if attempt + 1 < MAX_RETRIES {
                    agent_send_validation_error(&msg)?;
                    continue;
                }
                return Err(InquirerError::Validation(msg));
            }
            Ok(Err(e)) => return Err(e),
            Err(panic_payload) => {
                let msg = if let Some(s) = panic_payload.downcast_ref::<&str>() {
                    format!("Validator panicked: {s}")
                } else if let Some(s) = panic_payload.downcast_ref::<String>() {
                    format!("Validator panicked: {s}")
                } else {
                    "Validator panicked with an unknown payload".to_string()
                };
                return Err(InquirerError::Validation(msg));
            }
        }
    }
    Err(InquirerError::Validation("Max retries exceeded".into()))
}

#[cfg(test)]
pub fn reset_handshake() {
    // SAFETY: Only used in tests. Since Once is not resettable in std,
    // tests that need multiple handshakes should use separate processes.
    // For unit tests, we accept that handshake is sent only once.
}
