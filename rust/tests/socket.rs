//! Integration tests for Unix socket transport.
//!
//! These tests launch child processes that use the socket transport and
//! interact with them via `UnixStream`. Each test uses a unique socket
//! path to avoid interference.

#![cfg(unix)]

use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::os::unix::net::UnixStream;
use std::process::{Command, Stdio};
use std::time::Duration;

/// Helper: launch a child process running a shell script that uses cargo to
/// run inline Rust via a small helper binary. Instead, we use `cargo run --example`
/// or spawn `sh -c` scripts that exercise the socket.
///
/// We use `Command::new("sh")` with inline scripts that compile and run a
/// small Rust program using `cargo run`.
///
/// Read a JSON line from a `BufReader`, skipping empty lines.
fn read_json_line(reader: &mut BufReader<impl Read>) -> Value {
    let mut line = String::new();
    loop {
        line.clear();
        let n = reader.read_line(&mut line).expect("failed to read line");
        if n == 0 {
            panic!("unexpected EOF while reading JSON line");
        }
        let trimmed = line.trim();
        if !trimmed.is_empty() {
            return serde_json::from_str(trimmed)
                .unwrap_or_else(|e| panic!("failed to parse JSON: {e}\nline: {trimmed}"));
        }
    }
}

/// Create a unique socket path for a test.
fn unique_socket_path(test_name: &str) -> String {
    format!(
        "/tmp/inquirer-ai-test-{}-{}.sock",
        test_name,
        std::process::id()
    )
}

/// Get the path to the built test helper binary (built as an example).
fn helper_binary_path() -> String {
    // Build the helper
    let output = Command::new("cargo")
        .args(["build", "--example", "socket_test_helper"])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .output()
        .expect("failed to build socket_test_helper");
    if !output.status.success() {
        panic!(
            "Failed to build socket_test_helper:\n{}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    // Find the binary
    let target_dir = format!("{}/target/debug/examples", env!("CARGO_MANIFEST_DIR"));
    format!("{target_dir}/socket_test_helper")
}

/// Launch the helper binary with the given socket path and scenario.
fn launch_helper(socket_path: &str, scenario: &str) -> std::process::Child {
    let bin = helper_binary_path();
    Command::new(&bin)
        .env("INQUIRER_AI_MODE", "agent")
        .env("INQUIRER_AI_SOCKET", socket_path)
        .env("INQUIRER_AI_TRANSPORT", "socket")
        .env("TEST_SCENARIO", scenario)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap_or_else(|e| panic!("failed to launch {bin}: {e}"))
}

/// Wait for the socket file to appear (up to 5 seconds).
fn wait_for_socket(path: &str) {
    for _ in 0..100 {
        if std::path::Path::new(path).exists() {
            return;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    panic!("socket file {path} did not appear within 5 seconds");
}

/// Connect to the socket, read lines until we get a prompt.
fn connect_and_read_prompt(socket_path: &str) -> (UnixStream, Vec<Value>) {
    let stream = UnixStream::connect(socket_path)
        .unwrap_or_else(|e| panic!("failed to connect to {socket_path}: {e}"));
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .unwrap();

    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let mut messages = Vec::new();

    loop {
        let msg = read_json_line(&mut reader);
        let kind = msg.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        messages.push(msg.clone());
        if kind == "prompt" {
            break;
        }
    }

    (stream, messages)
}

// =========================================================================
// Test: basic prompt cycle
// =========================================================================

#[test]
fn socket_basic_prompt() {
    let sock_path = unique_socket_path("basic");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    // Read handshake from stdout
    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let handshake = read_json_line(&mut stdout_reader);

    assert_eq!(handshake["kind"], "handshake");
    assert_eq!(handshake["protocol"], "inquirer-ai");
    assert_eq!(handshake["socket"], sock_path);

    wait_for_socket(&sock_path);

    // Connect to socket
    let (mut stream, messages) = connect_and_read_prompt(&sock_path);

    // First connection gets handshake + prompt
    assert!(
        messages.len() >= 2,
        "expected handshake + prompt, got {messages:?}"
    );
    assert_eq!(messages[0]["kind"], "handshake");
    assert_eq!(messages[0]["socket"], sock_path);

    let prompt = messages.last().unwrap();
    assert_eq!(prompt["kind"], "prompt");
    assert_eq!(prompt["type"], "input");
    assert_eq!(prompt["step"], 1);

    // Send answer
    writeln!(stream, "{}", json!({"answer": "hello world"})).unwrap();
    stream.flush().unwrap();

    // Read response
    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let response = read_json_line(&mut reader);
    assert_eq!(response["status"], "accepted");

    // Wait for child to exit
    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");

    // Socket file should be cleaned up
    std::thread::sleep(Duration::from_millis(100));
    assert!(
        !std::path::Path::new(&sock_path).exists(),
        "socket file should be cleaned up"
    );
}

// =========================================================================
// Test: peek (connect then disconnect without answering)
// =========================================================================

#[test]
fn socket_peek_then_answer() {
    let sock_path = unique_socket_path("peek");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    // Read handshake from stdout
    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    // Peek: connect, read prompt, disconnect without answering
    {
        let (stream, messages) = connect_and_read_prompt(&sock_path);
        assert!(messages.iter().any(|m| m["kind"] == "prompt"));
        drop(stream);
    }

    // Now connect again and answer
    {
        let (mut stream, messages) = connect_and_read_prompt(&sock_path);
        // Second connection should NOT get handshake again, just prompt
        assert!(
            !messages.iter().any(|m| m["kind"] == "handshake"),
            "second connection should not get handshake"
        );
        let prompt = messages.last().unwrap();
        assert_eq!(prompt["kind"], "prompt");

        writeln!(stream, "{}", json!({"answer": "after peek"})).unwrap();
        stream.flush().unwrap();

        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let response = read_json_line(&mut reader);
        assert_eq!(response["status"], "accepted");
    }

    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");
}

// =========================================================================
// Test: validation retry on same connection
// =========================================================================

#[test]
fn socket_validation_retry() {
    let sock_path = unique_socket_path("valretry");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "number_min10");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    let (mut stream, _messages) = connect_and_read_prompt(&sock_path);

    // Send invalid answer (below min)
    writeln!(stream, "{}", json!({"answer": 5})).unwrap();
    stream.flush().unwrap();

    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let response = read_json_line(&mut reader);
    assert_eq!(response["kind"], "validation_error");

    // Send valid answer on same connection
    writeln!(stream, "{}", json!({"answer": 42})).unwrap();
    stream.flush().unwrap();

    let response = read_json_line(&mut reader);
    assert_eq!(response["status"], "accepted");

    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");
}

// =========================================================================
// Test: multi-prompt sequence
// =========================================================================

#[test]
fn socket_multi_prompt() {
    let sock_path = unique_socket_path("multi");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "multi_prompt");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    // Prompt 1: text
    {
        let (mut stream, messages) = connect_and_read_prompt(&sock_path);
        let prompt = messages.last().unwrap();
        assert_eq!(prompt["type"], "input");
        assert_eq!(prompt["step"], 1);

        writeln!(stream, "{}", json!({"answer": "Alice"})).unwrap();
        stream.flush().unwrap();

        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let response = read_json_line(&mut reader);
        assert_eq!(response["status"], "accepted");
    }

    // Prompt 2: confirm
    {
        let (mut stream, messages) = connect_and_read_prompt(&sock_path);
        let prompt = messages.last().unwrap();
        assert_eq!(prompt["type"], "confirm");
        assert_eq!(prompt["step"], 2);

        writeln!(stream, "{}", json!({"answer": true})).unwrap();
        stream.flush().unwrap();

        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let response = read_json_line(&mut reader);
        assert_eq!(response["status"], "accepted");
    }

    // Prompt 3: number
    {
        let (mut stream, messages) = connect_and_read_prompt(&sock_path);
        let prompt = messages.last().unwrap();
        assert_eq!(prompt["type"], "number");
        assert_eq!(prompt["step"], 3);

        writeln!(stream, "{}", json!({"answer": 42})).unwrap();
        stream.flush().unwrap();

        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let response = read_json_line(&mut reader);
        assert_eq!(response["status"], "accepted");
    }

    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");
}

// =========================================================================
// Test: socket cleanup on normal exit
// =========================================================================

#[test]
fn socket_cleanup_on_exit() {
    let sock_path = unique_socket_path("cleanup");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);
    assert!(std::path::Path::new(&sock_path).exists());

    // Answer the prompt so the process can exit
    {
        let (mut stream, _) = connect_and_read_prompt(&sock_path);
        writeln!(stream, "{}", json!({"answer": "done"})).unwrap();
        stream.flush().unwrap();
        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let _ = read_json_line(&mut reader);
    }

    let status = child.wait().unwrap();
    assert!(status.success());

    // Give cleanup a moment
    std::thread::sleep(Duration::from_millis(200));
    assert!(
        !std::path::Path::new(&sock_path).exists(),
        "socket file should be removed after exit"
    );
}

// =========================================================================
// Test: handshake_ack is handled gracefully
// =========================================================================

#[test]
fn socket_handshake_ack() {
    let sock_path = unique_socket_path("hshake_ack");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    let (mut stream, _messages) = connect_and_read_prompt(&sock_path);

    // Send handshake_ack followed by answer on the same line sequence
    writeln!(stream, "{}", json!({"kind": "handshake_ack"})).unwrap();
    writeln!(stream, "{}", json!({"answer": "acked"})).unwrap();
    stream.flush().unwrap();

    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let response = read_json_line(&mut reader);
    assert_eq!(response["status"], "accepted");

    let status = child.wait().unwrap();
    assert!(status.success());
}

// =========================================================================
// Lifecycle edge-case tests
// =========================================================================

#[test]
fn socket_rapid_reconnection() {
    let sock_path = unique_socket_path("rapid");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    // Peek: connect, read prompt, disconnect immediately
    {
        let (stream, messages) = connect_and_read_prompt(&sock_path);
        assert!(messages.iter().any(|m| m["kind"] == "prompt"));
        drop(stream);
    }

    // Immediately reconnect — no sleep
    {
        let (mut stream, messages) = connect_and_read_prompt(&sock_path);
        // Should not get handshake again
        assert!(
            !messages.iter().any(|m| m["kind"] == "handshake"),
            "second connection should not get handshake"
        );
        let prompt = messages.last().unwrap();
        assert_eq!(prompt["kind"], "prompt");

        writeln!(stream, "{}", json!({"answer": "rapid"})).unwrap();
        stream.flush().unwrap();

        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let response = read_json_line(&mut reader);
        assert_eq!(response["status"], "accepted");
    }

    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");
}

#[test]
fn socket_partial_message_no_newline() {
    let sock_path = unique_socket_path("partial");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    let (mut stream, _messages) = connect_and_read_prompt(&sock_path);

    // Send partial JSON without newline
    stream.write_all(b"{\"answer\": \"part").unwrap();
    stream.flush().unwrap();

    // Small delay then complete the line
    std::thread::sleep(Duration::from_millis(100));
    stream.write_all(b"ial\"}\n").unwrap();
    stream.flush().unwrap();

    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let response = read_json_line(&mut reader);
    assert_eq!(response["status"], "accepted");

    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");
}

#[test]
fn socket_multiple_clients_second_after_first() {
    let sock_path = unique_socket_path("multicli");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    // Client 1: peek
    {
        let (stream, messages) = connect_and_read_prompt(&sock_path);
        assert!(messages.iter().any(|m| m["kind"] == "prompt"));
        drop(stream);
    }

    // Client 2: answer
    {
        let (mut stream, messages) = connect_and_read_prompt(&sock_path);
        let prompt = messages.last().unwrap();
        assert_eq!(prompt["kind"], "prompt");

        writeln!(stream, "{}", json!({"answer": "client2"})).unwrap();
        stream.flush().unwrap();

        let mut reader = BufReader::new(stream.try_clone().unwrap());
        let response = read_json_line(&mut reader);
        assert_eq!(response["status"], "accepted");
    }

    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");
}

#[test]
fn socket_cleanup_on_sigterm() {
    let sock_path = unique_socket_path("sigterm");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);
    assert!(std::path::Path::new(&sock_path).exists());

    // Send SIGTERM instead of answering
    unsafe {
        libc::kill(child.id() as i32, libc::SIGTERM);
    }

    let _ = child.wait();
    std::thread::sleep(Duration::from_millis(200));

    assert!(
        !std::path::Path::new(&sock_path).exists(),
        "socket file should be removed after SIGTERM"
    );
}

#[test]
fn socket_large_payload() {
    let sock_path = unique_socket_path("large");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    // Drain stderr in background thread to prevent pipe buffer deadlock
    // (the child writes 100KB+ to stderr, which exceeds the OS pipe buffer)
    let stderr = child.stderr.take().unwrap();
    let stderr_handle = std::thread::spawn(move || {
        let mut buf = Vec::new();
        let mut reader = BufReader::new(stderr);
        let _ = reader.read_to_end(&mut buf);
        String::from_utf8_lossy(&buf).to_string()
    });

    wait_for_socket(&sock_path);

    let (mut stream, _messages) = connect_and_read_prompt(&sock_path);

    // Build a 100 KB+ string
    let large_value: String = "x".repeat(100 * 1024);
    let payload = json!({"answer": large_value});
    writeln!(stream, "{}", payload).unwrap();
    stream.flush().unwrap();

    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let response = read_json_line(&mut reader);
    assert_eq!(response["status"], "accepted");

    let status = child.wait().unwrap();
    assert!(status.success(), "child exited with: {status}");

    let stderr_output = stderr_handle.join().unwrap();
    assert!(stderr_output.contains("Got:"), "expected Got: in stderr");
    assert!(
        stderr_output.contains(&large_value[..20]),
        "expected large payload in stderr"
    );
}

// =========================================================================
// Test: missing answer key triggers validation error
// =========================================================================

#[test]
fn socket_missing_answer_key() {
    let sock_path = unique_socket_path("nokey");
    let _ = std::fs::remove_file(&sock_path);

    let mut child = launch_helper(&sock_path, "single_text");

    let stdout = child.stdout.take().unwrap();
    let mut stdout_reader = BufReader::new(stdout);
    let _handshake = read_json_line(&mut stdout_reader);

    wait_for_socket(&sock_path);

    let (mut stream, _messages) = connect_and_read_prompt(&sock_path);

    // Send JSON without "answer" key
    writeln!(stream, "{}", json!({"value": "oops"})).unwrap();
    stream.flush().unwrap();

    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let response = read_json_line(&mut reader);
    assert_eq!(response["kind"], "validation_error");
    assert!(response["message"].as_str().unwrap().contains("answer"));

    // Now send valid answer
    writeln!(stream, "{}", json!({"answer": "correct"})).unwrap();
    stream.flush().unwrap();

    let response = read_json_line(&mut reader);
    assert_eq!(response["status"], "accepted");

    let status = child.wait().unwrap();
    assert!(status.success());
}
