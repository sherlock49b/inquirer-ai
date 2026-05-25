//! Unix socket transport for agent mode.
//!
//! When agent mode is active, the CLI creates a Unix domain socket and
//! advertises its path in the handshake on stdout. Each socket connection
//! handles exactly one prompt-answer cycle. Agents interact using
//! independent bash commands (`nc -U` or `socat`), one per prompt.

#[cfg(unix)]
mod inner {
    use crate::errors::{InquirerError, Result};
    use serde_json::Value;
    use std::io::{BufRead, BufReader, Write};
    use std::os::unix::net::{UnixListener, UnixStream};
    use std::panic::{catch_unwind, AssertUnwindSafe};
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
    use std::sync::OnceLock;

    const VERSION: &str = "0.2.1";
    const MAX_RETRIES: usize = 3;

    /// Singleton socket transport instance.
    static TRANSPORT: OnceLock<Option<SocketTransport>> = OnceLock::new();

    /// Path stored for signal handler cleanup (signal-safe: fixed buffer, no alloc).
    static CLEANUP_PATH: OnceLock<String> = OnceLock::new();

    /// Unix socket transport for the inquirer-ai agent protocol.
    ///
    /// Manages a Unix domain socket server that accepts one connection per
    /// prompt cycle. The handshake is sent to stdout on creation and to the
    /// first socket connection.
    pub struct SocketTransport {
        listener: UnixListener,
        path: String,
        stdout_handshake_sent: bool,
        socket_handshake_sent: AtomicBool,
        step: AtomicUsize,
    }

    impl SocketTransport {
        /// Create a new socket transport, binding to the given path.
        ///
        /// Removes any stale socket file before binding. Sends the handshake
        /// to stdout immediately.
        pub fn new(path: Option<&str>) -> Result<Self> {
            let socket_path = path
                .map(|p| p.to_string())
                .unwrap_or_else(|| format!("/tmp/inquirer-ai-{}.sock", std::process::id()));

            // Remove stale socket if it exists
            let _ = std::fs::remove_file(&socket_path);

            let listener = UnixListener::bind(&socket_path).map_err(|e| {
                InquirerError::Io(std::io::Error::new(
                    e.kind(),
                    format!("Failed to bind Unix socket at {socket_path}: {e}"),
                ))
            })?;

            let mut transport = SocketTransport {
                listener,
                path: socket_path,
                stdout_handshake_sent: false,
                socket_handshake_sent: AtomicBool::new(false),
                step: AtomicUsize::new(0),
            };

            transport.send_stdout_handshake()?;

            // Store path for cleanup handlers
            let _ = CLEANUP_PATH.set(transport.path.clone());

            // Register atexit cleanup
            unsafe {
                libc::atexit(atexit_cleanup);
            }

            // Install SIGTERM handler
            unsafe {
                libc::signal(
                    libc::SIGTERM,
                    sigterm_handler as *const () as libc::sighandler_t,
                );
            }

            Ok(transport)
        }

        /// Get the socket path.
        pub fn path(&self) -> &str {
            &self.path
        }

        fn handshake_payload(&self) -> Value {
            serde_json::json!({
                "kind": "handshake",
                "protocol": "inquirer-ai",
                "version": VERSION,
                "format": "jsonl",
                "socket": self.path,
                "interaction": "sequential",
                "total": null,
                "description": concat!(
                    "Interactive prompt protocol over Unix socket. ",
                    "Connect to read a prompt, send a JSON answer, receive status. ",
                    "One connection per prompt."
                ),
                "example_response": {"answer": "<value>"}
            })
        }

        fn send_stdout_handshake(&mut self) -> Result<()> {
            if self.stdout_handshake_sent {
                return Ok(());
            }
            self.stdout_handshake_sent = true;
            let payload = self.handshake_payload();
            let mut stdout = std::io::stdout().lock();
            writeln!(stdout, "{}", serde_json::to_string(&payload).unwrap())?;
            stdout.flush()?;
            Ok(())
        }

        fn write_json(stream: &mut UnixStream, value: &Value) -> Result<()> {
            let line = serde_json::to_string(value).unwrap();
            writeln!(stream, "{line}")?;
            stream.flush()?;
            Ok(())
        }

        /// Execute a single prompt-answer cycle over the socket.
        ///
        /// Accepts connections, sends the prompt, reads answers, validates,
        /// and retries on validation errors (up to `MAX_RETRIES` total).
        /// If the client disconnects without answering, the prompt is
        /// re-queued for the next connection.
        pub fn prompt_cycle<T>(
            &self,
            payload: &Value,
            validate: impl Fn(Value) -> Result<T>,
        ) -> Result<T> {
            let step = self.step.fetch_add(1, Ordering::SeqCst) + 1;

            // Merge step into payload
            let mut obj = match payload {
                Value::Object(map) => map.clone(),
                _ => serde_json::Map::new(),
            };
            obj.insert("kind".to_string(), Value::String("prompt".to_string()));
            obj.insert("step".to_string(), Value::Number(step.into()));
            obj.insert("total".to_string(), Value::Null);
            let prompt_payload = Value::Object(obj);

            let mut retries_used: usize = 0;

            while retries_used < MAX_RETRIES {
                let (mut stream, _) = self.listener.accept()?;

                // Send handshake on first connection
                if !self.socket_handshake_sent.swap(true, Ordering::SeqCst) {
                    let handshake = self.handshake_payload();
                    if Self::write_json(&mut stream, &handshake).is_err() {
                        continue;
                    }
                }

                // Send prompt
                if Self::write_json(&mut stream, &prompt_payload).is_err() {
                    continue;
                }

                let reader = BufReader::new(stream.try_clone()?);
                let mut lines = reader.lines();

                // Inner retry loop on the same connection
                while retries_used < MAX_RETRIES {
                    let line = match lines.next() {
                        Some(Ok(line)) if !line.trim().is_empty() => line,
                        _ => {
                            // Client disconnected without answering: re-queue
                            break;
                        }
                    };

                    let line = line.trim().to_string();

                    // Parse JSON
                    let parsed: Value = match serde_json::from_str(&line) {
                        Ok(v) => v,
                        Err(_) => {
                            retries_used += 1;
                            let msg = format!("Invalid JSON: {line}");
                            if retries_used >= MAX_RETRIES {
                                let _ = Self::write_json(
                                    &mut stream,
                                    &serde_json::json!({"kind": "error", "message": msg}),
                                );
                                return Err(InquirerError::Validation(msg));
                            }
                            let _ = Self::write_json(
                                &mut stream,
                                &serde_json::json!({"kind": "validation_error", "message": msg}),
                            );
                            continue;
                        }
                    };

                    // Handle handshake_ack: skip it and read the next line
                    let parsed = if parsed.get("kind").and_then(|v| v.as_str())
                        == Some("handshake_ack")
                    {
                        match lines.next() {
                            Some(Ok(line)) if !line.trim().is_empty() => {
                                match serde_json::from_str(line.trim()) {
                                    Ok(v) => v,
                                    Err(_) => {
                                        retries_used += 1;
                                        let msg = format!("Invalid JSON: {}", line.trim());
                                        if retries_used >= MAX_RETRIES {
                                            let _ = Self::write_json(
                                                &mut stream,
                                                &serde_json::json!({"kind": "error", "message": msg}),
                                            );
                                            return Err(InquirerError::Validation(msg));
                                        }
                                        let _ = Self::write_json(
                                            &mut stream,
                                            &serde_json::json!({"kind": "validation_error", "message": msg}),
                                        );
                                        continue;
                                    }
                                }
                            }
                            _ => break, // Client disconnected
                        }
                    } else {
                        parsed
                    };

                    // Check for "answer" key
                    if !parsed.is_object() || parsed.get("answer").is_none() {
                        retries_used += 1;
                        let msg =
                            "Response must be a JSON object with an \"answer\" key".to_string();
                        if retries_used >= MAX_RETRIES {
                            let _ = Self::write_json(
                                &mut stream,
                                &serde_json::json!({"kind": "error", "message": msg}),
                            );
                            return Err(InquirerError::Validation(msg));
                        }
                        let _ = Self::write_json(
                            &mut stream,
                            &serde_json::json!({"kind": "validation_error", "message": msg}),
                        );
                        continue;
                    }

                    let answer = parsed.get("answer").unwrap().clone();

                    // Validate with catch_unwind
                    let result = catch_unwind(AssertUnwindSafe(|| validate(answer)));

                    match result {
                        Ok(Ok(val)) => {
                            let _ = Self::write_json(
                                &mut stream,
                                &serde_json::json!({"status": "accepted"}),
                            );
                            return Ok(val);
                        }
                        Ok(Err(InquirerError::Validation(msg))) => {
                            retries_used += 1;
                            if retries_used >= MAX_RETRIES {
                                let _ = Self::write_json(
                                    &mut stream,
                                    &serde_json::json!({"kind": "error", "message": msg}),
                                );
                                return Err(InquirerError::Validation(msg));
                            }
                            let _ = Self::write_json(
                                &mut stream,
                                &serde_json::json!({"kind": "validation_error", "message": msg}),
                            );
                            continue;
                        }
                        Ok(Err(e)) => {
                            let _ = Self::write_json(
                                &mut stream,
                                &serde_json::json!({"kind": "error", "message": e.to_string()}),
                            );
                            return Err(e);
                        }
                        Err(panic_payload) => {
                            let msg = if let Some(s) = panic_payload.downcast_ref::<&str>() {
                                format!("Validator panicked: {s}")
                            } else if let Some(s) = panic_payload.downcast_ref::<String>() {
                                format!("Validator panicked: {s}")
                            } else {
                                "Validator panicked with an unknown payload".to_string()
                            };
                            let _ = Self::write_json(
                                &mut stream,
                                &serde_json::json!({"kind": "error", "message": msg}),
                            );
                            return Err(InquirerError::Validation(msg));
                        }
                    }
                }
            }

            Err(InquirerError::Validation(
                "Maximum validation retries exceeded".into(),
            ))
        }
    }

    impl Drop for SocketTransport {
        fn drop(&mut self) {
            let _ = std::fs::remove_file(&self.path);
        }
    }

    // -- Cleanup handlers (module-level so they share the same CLEANUP_PATH) --

    extern "C" fn atexit_cleanup() {
        if let Some(path) = CLEANUP_PATH.get() {
            let _ = std::fs::remove_file(path);
        }
    }

    extern "C" fn sigterm_handler(_sig: libc::c_int) {
        if let Some(path) = CLEANUP_PATH.get() {
            let _ = std::fs::remove_file(path.as_str());
        }
        unsafe {
            libc::_exit(0);
        }
    }

    /// Get or initialize the global socket transport singleton.
    ///
    /// Returns `None` if:
    /// - `INQUIRER_AI_MODE=human` is set
    /// - `INQUIRER_AI_TRANSPORT=stdio` is set
    /// - Agent mode is not active
    ///
    /// Returns `Some(&SocketTransport)` when socket transport should be used.
    pub fn get_socket_transport() -> Option<&'static SocketTransport> {
        TRANSPORT
            .get_or_init(|| {
                let env_mode = std::env::var("INQUIRER_AI_MODE")
                    .unwrap_or_default()
                    .to_lowercase();
                if env_mode == "human" {
                    return None;
                }

                // Skip socket creation if INQUIRER_AI_TRANSPORT=stdio
                if std::env::var("INQUIRER_AI_TRANSPORT")
                    .unwrap_or_default()
                    .to_lowercase()
                    == "stdio"
                {
                    return None;
                }

                // If INQUIRER_AI_SOCKET is set, use that path
                if let Ok(path) = std::env::var("INQUIRER_AI_SOCKET") {
                    if !path.is_empty() {
                        return SocketTransport::new(Some(&path)).ok();
                    }
                }

                // Otherwise, auto-create only when in agent mode
                if crate::mode::is_agent_mode() {
                    return SocketTransport::new(None).ok();
                }

                None
            })
            .as_ref()
    }
}

#[cfg(unix)]
pub use inner::*;

#[cfg(not(unix))]
mod inner {
    use crate::errors::Result;
    use serde_json::Value;

    pub struct SocketTransport;

    impl SocketTransport {
        pub fn prompt_cycle<T>(
            &self,
            _payload: &Value,
            _validate: impl Fn(Value) -> Result<T>,
        ) -> Result<T> {
            unreachable!("socket transport not available on this platform")
        }
    }

    pub fn get_socket_transport() -> Option<&'static SocketTransport> {
        None
    }
}

#[cfg(not(unix))]
pub use inner::*;
