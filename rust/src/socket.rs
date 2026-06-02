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
    use std::os::unix::fs::PermissionsExt;
    use std::os::unix::net::{UnixListener, UnixStream};
    use std::panic::{catch_unwind, AssertUnwindSafe};
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
    use std::sync::OnceLock;

    const VERSION: &str = env!("CARGO_PKG_VERSION");
    const MAX_RETRIES: usize = 3;

    /// Maximum length of a single answer line accepted over the socket.
    /// Lines longer than this are rejected with a validation error.
    const MAX_LINE_BYTES: u64 = 1_048_576;

    /// Maximum length of a `sun_path` for an explicit socket path.
    const SUN_PATH_MAX: usize = 104;

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
            let socket_path = match path {
                Some(p) => {
                    validate_explicit_socket_path(p)?;
                    p.to_string()
                }
                None => format!("/tmp/inquirer-ai-{}.sock", std::process::id()),
            };

            // Stale-socket cleanup: lstat (do NOT follow symlinks). If the path
            // exists and is a socket, unlink it. If it exists and is NOT a
            // socket (regular file/dir/symlink), refuse to start — never
            // unlink a non-socket.
            prepare_socket_path(&socket_path)?;

            let listener = UnixListener::bind(&socket_path).map_err(|e| {
                InquirerError::Io(std::io::Error::new(
                    e.kind(),
                    format!("Failed to bind Unix socket at {socket_path}: {e}"),
                ))
            })?;

            // Restrict the socket to the owner (0600).
            if let Err(e) =
                std::fs::set_permissions(&socket_path, std::fs::Permissions::from_mode(0o600))
            {
                let _ = std::fs::remove_file(&socket_path);
                return Err(InquirerError::Io(std::io::Error::new(
                    e.kind(),
                    format!("Failed to chmod socket {socket_path}: {e}"),
                )));
            }

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

            // Install SIGTERM and SIGINT handlers. `atexit` does not run on a
            // default signal disposition, so we handle both signals to ensure
            // the socket file is removed on Ctrl-C and on termination.
            unsafe {
                libc::signal(
                    libc::SIGTERM,
                    signal_cleanup_handler as *const () as libc::sighandler_t,
                );
                libc::signal(
                    libc::SIGINT,
                    signal_cleanup_handler as *const () as libc::sighandler_t,
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

                // Send handshake on first connection. Only mark the handshake
                // as sent once the write actually succeeds, so a failed write
                // does not suppress the handshake on the next connection.
                if !self.socket_handshake_sent.load(Ordering::SeqCst) {
                    let handshake = self.handshake_payload();
                    if Self::write_json(&mut stream, &handshake).is_err() {
                        continue;
                    }
                    self.socket_handshake_sent.store(true, Ordering::SeqCst);
                }

                // Send prompt
                if Self::write_json(&mut stream, &prompt_payload).is_err() {
                    continue;
                }

                let mut reader = BufReader::new(stream.try_clone()?);

                // Inner retry loop on the same connection
                while retries_used < MAX_RETRIES {
                    let line = match read_capped_line(&mut reader) {
                        ReadLine::Line(line) => line,
                        ReadLine::TooLong => {
                            // Oversized line: consume a retry, report, continue.
                            retries_used += 1;
                            let msg = format!(
                                "Answer line exceeds maximum size of {MAX_LINE_BYTES} bytes"
                            );
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
                        ReadLine::Eof => {
                            // Client disconnected without answering: re-queue
                            break;
                        }
                    };

                    // Parse JSON. Never crash on untrusted input.
                    let parsed: Value = match serde_json::from_str(&line) {
                        Ok(v) => v,
                        Err(e) => {
                            retries_used += 1;
                            let msg = format!("Invalid JSON response: {e}");
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
                        match read_capped_line(&mut reader) {
                            ReadLine::Line(next) => match serde_json::from_str(&next) {
                                Ok(v) => v,
                                Err(e) => {
                                    retries_used += 1;
                                    let msg = format!("Invalid JSON response: {e}");
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
                            },
                            ReadLine::TooLong => {
                                retries_used += 1;
                                let msg = format!(
                                    "Answer line exceeds maximum size of {MAX_LINE_BYTES} bytes"
                                );
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
                            ReadLine::Eof => break, // Client disconnected
                        }
                    } else {
                        parsed
                    };

                    // Check for "answer" key
                    if !parsed.is_object() || parsed.get("answer").is_none() {
                        retries_used += 1;
                        let msg =
                            "Answer must be a JSON object with an \"answer\" field".to_string();
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

    // NOTE: `SocketTransport` is only ever created as the single value held by
    // the `TRANSPORT` static (see `get_socket_transport`), which is never
    // dropped during normal operation — cleanup happens via the `atexit` and
    // signal handlers below. This `Drop` impl exists so that explicit
    // construction in tests (and any future non-singleton use) still removes
    // the socket file.
    impl Drop for SocketTransport {
        fn drop(&mut self) {
            let _ = std::fs::remove_file(&self.path);
        }
    }

    /// Validate an explicitly-provided `INQUIRER_AI_SOCKET` path: it must be a
    /// non-empty absolute path, shorter than the `sun_path` limit, with an
    /// existing parent directory.
    fn validate_explicit_socket_path(path: &str) -> Result<()> {
        if path.is_empty() {
            return Err(InquirerError::Io(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "INQUIRER_AI_SOCKET must not be empty",
            )));
        }
        if !std::path::Path::new(path).is_absolute() {
            return Err(InquirerError::Io(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                format!("INQUIRER_AI_SOCKET must be an absolute path: {path}"),
            )));
        }
        if path.len() >= SUN_PATH_MAX {
            return Err(InquirerError::Io(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                format!(
                    "INQUIRER_AI_SOCKET path too long ({} bytes, max {}): {path}",
                    path.len(),
                    SUN_PATH_MAX - 1
                ),
            )));
        }
        match std::path::Path::new(path).parent() {
            Some(parent) if !parent.as_os_str().is_empty() && !parent.is_dir() => {
                Err(InquirerError::Io(std::io::Error::new(
                    std::io::ErrorKind::NotFound,
                    format!("INQUIRER_AI_SOCKET parent directory does not exist: {path}"),
                )))
            }
            _ => Ok(()),
        }
    }

    /// Prepare the socket path for binding: lstat the path WITHOUT following
    /// symlinks; if it exists and is a socket, unlink it (stale cleanup); if it
    /// exists and is not a socket, refuse to start.
    fn prepare_socket_path(path: &str) -> Result<()> {
        match std::fs::symlink_metadata(path) {
            Ok(meta) => {
                use std::os::unix::fs::FileTypeExt;
                if meta.file_type().is_socket() {
                    std::fs::remove_file(path).map_err(|e| {
                        InquirerError::Io(std::io::Error::new(
                            e.kind(),
                            format!("Failed to remove stale socket {path}: {e}"),
                        ))
                    })
                } else {
                    Err(InquirerError::Io(std::io::Error::new(
                        std::io::ErrorKind::AlreadyExists,
                        format!(
                            "Refusing to bind: {path} exists and is not a socket; \
                             remove it or choose another INQUIRER_AI_SOCKET path"
                        ),
                    )))
                }
            }
            // Path does not exist (or cannot be stat'd) — nothing to clean up.
            Err(ref e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(e) => Err(InquirerError::Io(std::io::Error::new(
                e.kind(),
                format!("Failed to inspect socket path {path}: {e}"),
            ))),
        }
    }

    /// Result of reading one line from the socket with a size cap.
    enum ReadLine {
        /// A non-empty trimmed line.
        Line(String),
        /// The line exceeded `MAX_LINE_BYTES`.
        TooLong,
        /// EOF / disconnect (or only blank lines until EOF).
        Eof,
    }

    /// Read a single newline-terminated line, skipping blank lines, capping the
    /// total bytes consumed at `MAX_LINE_BYTES`. Reading byte-by-byte through
    /// the `BufReader` keeps memory bounded even for an unterminated flood.
    fn read_capped_line<R: BufRead>(reader: &mut R) -> ReadLine {
        loop {
            let mut buf: Vec<u8> = Vec::new();
            // read_until honours the buffer cap by us tracking length manually.
            let mut byte = [0u8; 1];
            loop {
                match reader.read(&mut byte) {
                    Ok(0) => {
                        // EOF: if we accumulated only whitespace, treat as EOF.
                        if buf.is_empty() {
                            return ReadLine::Eof;
                        }
                        break;
                    }
                    Ok(_) => {
                        if byte[0] == b'\n' {
                            break;
                        }
                        buf.push(byte[0]);
                        if buf.len() as u64 > MAX_LINE_BYTES {
                            // Drain the rest of the oversized line up to the
                            // next newline (bounded best-effort) and report.
                            drain_to_newline(reader);
                            return ReadLine::TooLong;
                        }
                    }
                    Err(_) => return ReadLine::Eof,
                }
            }

            let line = String::from_utf8_lossy(&buf).trim().to_string();
            if line.is_empty() {
                // Skip blank lines and keep reading.
                if buf.is_empty() {
                    return ReadLine::Eof;
                }
                continue;
            }
            return ReadLine::Line(line);
        }
    }

    /// Best-effort consume bytes until the next newline or EOF, capped so a
    /// malicious client cannot make us spin forever on an unterminated flood.
    fn drain_to_newline<R: BufRead>(reader: &mut R) {
        let mut byte = [0u8; 1];
        let mut drained: u64 = 0;
        while drained < MAX_LINE_BYTES {
            match reader.read(&mut byte) {
                Ok(0) => return,
                Ok(_) => {
                    drained += 1;
                    if byte[0] == b'\n' {
                        return;
                    }
                }
                Err(_) => return,
            }
        }
    }

    // -- Cleanup handlers (module-level so they share the same CLEANUP_PATH) --

    extern "C" fn atexit_cleanup() {
        if let Some(path) = CLEANUP_PATH.get() {
            let _ = std::fs::remove_file(path);
        }
    }

    extern "C" fn signal_cleanup_handler(_sig: libc::c_int) {
        if let Some(path) = CLEANUP_PATH.get() {
            let _ = std::fs::remove_file(path.as_str());
        }
        unsafe {
            libc::_exit(0);
        }
    }

    /// Get or initialize the global socket transport singleton.
    ///
    /// Implements the transport-selection contract (R3). The socket transport
    /// is used iff the process is in agent mode AND a socket was requested
    /// (`INQUIRER_AI_SOCKET` set, or `INQUIRER_AI_MODE=agent`) AND
    /// `INQUIRER_AI_TRANSPORT` is not "stdio". Otherwise the stdio agent
    /// transport (or terminal mode) is used and this returns `None`.
    ///
    /// The socket path is `INQUIRER_AI_SOCKET` if set, otherwise
    /// `/tmp/inquirer-ai-{pid}.sock`.
    pub fn get_socket_transport() -> Option<&'static SocketTransport> {
        TRANSPORT
            .get_or_init(|| {
                // Only relevant in agent mode.
                if !crate::mode::is_agent_mode() {
                    return None;
                }

                // A socket must have been explicitly requested.
                if !crate::mode::is_socket_requested() {
                    return None;
                }

                // Explicit opt-out: INQUIRER_AI_TRANSPORT=stdio forces stdio.
                if std::env::var("INQUIRER_AI_TRANSPORT")
                    .unwrap_or_default()
                    .eq_ignore_ascii_case("stdio")
                {
                    return None;
                }

                // Socket path: INQUIRER_AI_SOCKET if set & non-empty, else default.
                match std::env::var("INQUIRER_AI_SOCKET") {
                    Ok(path) if !path.is_empty() => SocketTransport::new(Some(&path)).ok(),
                    _ => SocketTransport::new(None).ok(),
                }
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
