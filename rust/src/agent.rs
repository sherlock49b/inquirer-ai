use crate::errors::{InquirerError, Result};
use serde_json::Value;
use std::io::{self, BufRead, Write};
use std::sync::Once;

static HANDSHAKE: Once = Once::new();
const VERSION: &str = "0.1.0";

fn send_handshake() {
    HANDSHAKE.call_once(|| {
        let meta = serde_json::json!({
            "protocol": "inquirer-ai",
            "version": VERSION,
            "format": "jsonl",
            "interaction": "sequential",
            "description": concat!(
                "Interactive prompt protocol. Prompts are sent one at a time — ",
                "read one JSON line from stdout, respond with one JSON line on stdin, ",
                "then wait for the next prompt. Do NOT send all answers at once. ",
                "Use a named pipe (mkfifo) or line-buffered I/O for bidirectional communication."
            ),
            "example_response": {"answer": "<value>"}
        });
        let mut stdout = io::stdout().lock();
        let _ = writeln!(stdout, "{}", meta);
        let _ = stdout.flush();
    });
}

pub fn agent_send(payload: &Value) -> Result<()> {
    send_handshake();
    let mut stdout = io::stdout().lock();
    writeln!(stdout, "{payload}")?;
    stdout.flush()?;
    Ok(())
}

pub fn agent_receive() -> Result<Value> {
    let stdin = io::stdin();
    let mut line = String::new();
    let bytes = stdin.lock().read_line(&mut line)?;
    if bytes == 0 {
        return Err(InquirerError::PromptAborted(
            "No response received (stdin closed). Expected JSON like: {\"answer\": \"<value>\"}"
                .to_string(),
        ));
    }

    let resp: Value = serde_json::from_str(line.trim()).map_err(|e| {
        InquirerError::Validation(format!(
            "Invalid JSON response: {e}. Expected JSON like: {{\"answer\": \"<value>\"}}"
        ))
    })?;

    match resp.get("answer") {
        Some(answer) => Ok(answer.clone()),
        None => Err(InquirerError::Validation(
            "Response must be a JSON object with an \"answer\" key".to_string(),
        )),
    }
}

#[cfg(test)]
pub fn reset_handshake() {
    // SAFETY: Only used in tests. Since Once is not resettable in std,
    // tests that need multiple handshakes should use separate processes.
    // For unit tests, we accept that handshake is sent only once.
}
