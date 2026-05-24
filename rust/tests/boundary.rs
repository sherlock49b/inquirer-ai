//! Boundary condition tests for inquirer-ai.
//!
//! Covers: invalid fd fallback, all-disabled choices, empty choice list,
//! and stdin EOF handling.

use inquirer_ai::choice::{Choice, ChoiceItem};
use inquirer_ai::errors::InquirerError;
use serde_json::json;

// =========================================================================
// Fix 1: Invalid fd environment variables — should fall back, not UB
// =========================================================================

/// Spawns a child process that sets INQUIRER_AI_FD_OUT to a bogus fd (999)
/// and attempts to use it. The library should detect that fd 999 is not open,
/// fall back to stdout, and not trigger undefined behavior.
#[test]
fn invalid_fd_env_falls_back_gracefully() {
    // We test this in a subprocess to avoid polluting env for other tests
    // and because from_raw_fd takes ownership.
    let exe = std::env::current_exe().unwrap();
    let output = std::process::Command::new(exe)
        .arg("--ignored")
        .arg("invalid_fd_subprocess_helper")
        .env("INQUIRER_AI_FD_OUT", "999")
        .env("INQUIRER_AI_FD_IN", "999")
        .env("INQUIRER_AI_MODE", "agent")
        .env("RUN_INVALID_FD_HELPER", "1")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .output()
        .expect("Failed to spawn subprocess");

    // The subprocess should exit successfully (not crash/SIGILL/SIGSEGV).
    // It will fail with a validation or IO error, which is fine — the point
    // is it does not invoke UB.
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    // Check it didn't crash with a signal (which would indicate UB)
    assert!(
        !matches!(output.status.code(), None),
        "Subprocess was killed by signal (likely UB). stderr: {stderr}"
    );

    // We expect exit code 0 (our helper catches the error)
    assert_eq!(
        output.status.code(),
        Some(0),
        "Subprocess failed unexpectedly. stdout: {stdout}, stderr: {stderr}"
    );
}

/// This test is only run as a subprocess helper by `invalid_fd_env_falls_back_gracefully`.
/// It is ignored in normal test runs.
#[test]
#[ignore]
fn invalid_fd_subprocess_helper() {
    if std::env::var("RUN_INVALID_FD_HELPER").is_err() {
        return;
    }

    // With INQUIRER_AI_FD_OUT=999 and INQUIRER_AI_FD_IN=999 set by the parent,
    // the library should detect invalid fds and fall back to stdout/stdin.
    // agent_send will try to write to the fd (should fall back to stdout).
    // We don't care about the result — just that it doesn't crash.
    let payload = json!({
        "type": "confirm",
        "message": "test",
    });
    // This will likely fail with PromptAborted (stdin is piped but empty),
    // or succeed writing to stdout. Either way, no UB.
    let _ = inquirer_ai::agent::agent_send(&payload);
    // Try reading too — will get EOF from piped stdin, that's fine.
    let result = inquirer_ai::agent::agent_receive();
    match result {
        Err(InquirerError::PromptAborted(_)) => {} // expected: stdin piped with no data
        Err(_) => {}                               // any error is acceptable
        Ok(_) => {}                                // would be surprising but not wrong
    }
}

// =========================================================================
// Fix 1 (unit-level): Direct fd validation test via subprocess
// =========================================================================

/// Verifies that setting INQUIRER_AI_FD_OUT to a non-numeric string
/// also falls back gracefully.
#[test]
fn non_numeric_fd_env_falls_back_gracefully() {
    let exe = std::env::current_exe().unwrap();
    let output = std::process::Command::new(exe)
        .arg("--ignored")
        .arg("non_numeric_fd_subprocess_helper")
        .env("INQUIRER_AI_FD_OUT", "not_a_number")
        .env("INQUIRER_AI_FD_IN", "garbage")
        .env("INQUIRER_AI_MODE", "agent")
        .env("RUN_NON_NUMERIC_FD_HELPER", "1")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .output()
        .expect("Failed to spawn subprocess");

    assert!(
        output.status.code().is_some(),
        "Subprocess was killed by signal"
    );
    assert_eq!(output.status.code(), Some(0));
}

#[test]
#[ignore]
fn non_numeric_fd_subprocess_helper() {
    if std::env::var("RUN_NON_NUMERIC_FD_HELPER").is_err() {
        return;
    }
    let payload = json!({ "type": "confirm", "message": "test" });
    let _ = inquirer_ai::agent::agent_send(&payload);
    let result = inquirer_ai::agent::agent_receive();
    match result {
        Err(InquirerError::PromptAborted(_)) => {}
        Err(_) => {}
        Ok(_) => {}
    }
}

// =========================================================================
// All choices disabled — should return InvalidChoice error
// =========================================================================

#[test]
fn select_all_disabled_returns_invalid_choice() {
    let mut c1 = Choice::new("Option A", json!("a"));
    c1.disabled = Some(json!(true));
    let mut c2 = Choice::new("Option B", json!("b"));
    c2.disabled = Some(json!("Not available"));

    let choices = vec![ChoiceItem::Choice(c1), ChoiceItem::Choice(c2)];

    let config = inquirer_ai::SelectConfig::new("Pick one", choices);
    let result = inquirer_ai::prompts::select::select(config);

    match result {
        Err(InquirerError::InvalidChoice(msg)) => {
            assert!(
                msg.contains("selectable"),
                "Error message should mention selectable items, got: {msg}"
            );
        }
        other => panic!("Expected InvalidChoice error, got: {other:?}"),
    }
}

#[test]
fn checkbox_all_disabled_returns_invalid_choice() {
    let mut c1 = Choice::new("Option A", json!("a"));
    c1.disabled = Some(json!(true));
    let mut c2 = Choice::new("Option B", json!("b"));
    c2.disabled = Some(json!("Unavailable"));

    let choices = vec![ChoiceItem::Choice(c1), ChoiceItem::Choice(c2)];

    let config = inquirer_ai::CheckboxConfig::new("Check some", choices);
    let result = inquirer_ai::prompts::checkbox::checkbox(config);

    match result {
        Err(InquirerError::InvalidChoice(msg)) => {
            assert!(
                msg.contains("selectable"),
                "Error message should mention selectable items, got: {msg}"
            );
        }
        other => panic!("Expected InvalidChoice error, got: {other:?}"),
    }
}

// =========================================================================
// Empty choice list — should return InvalidChoice error
// =========================================================================

#[test]
fn select_empty_choices_returns_invalid_choice() {
    let config = inquirer_ai::SelectConfig::new("Pick one", vec![]);
    let result = inquirer_ai::prompts::select::select(config);

    match result {
        Err(InquirerError::InvalidChoice(msg)) => {
            assert!(
                msg.contains("selectable"),
                "Error message should mention selectable items, got: {msg}"
            );
        }
        other => panic!("Expected InvalidChoice error, got: {other:?}"),
    }
}

#[test]
fn checkbox_empty_choices_returns_invalid_choice() {
    let config = inquirer_ai::CheckboxConfig::new("Check some", vec![]);
    let result = inquirer_ai::prompts::checkbox::checkbox(config);

    match result {
        Err(InquirerError::InvalidChoice(msg)) => {
            assert!(
                msg.contains("selectable"),
                "Error message should mention selectable items, got: {msg}"
            );
        }
        other => panic!("Expected InvalidChoice error, got: {other:?}"),
    }
}

// =========================================================================
// Separators-only choice list — should also be InvalidChoice
// =========================================================================

#[test]
fn select_only_separators_returns_invalid_choice() {
    let choices = vec![
        ChoiceItem::Separator(inquirer_ai::Separator::default()),
        ChoiceItem::Separator(inquirer_ai::Separator::new("Section 2")),
    ];
    let config = inquirer_ai::SelectConfig::new("Pick one", choices);
    let result = inquirer_ai::prompts::select::select(config);

    match result {
        Err(InquirerError::InvalidChoice(_)) => {} // expected
        other => panic!("Expected InvalidChoice error, got: {other:?}"),
    }
}

// =========================================================================
// stdin EOF — should return PromptAborted error
// =========================================================================

/// Spawn a subprocess in agent mode with stdin immediately closed (EOF).
/// The library should return PromptAborted, not hang or crash.
#[test]
fn stdin_eof_returns_prompt_aborted() {
    let exe = std::env::current_exe().unwrap();
    let output = std::process::Command::new(exe)
        .arg("--ignored")
        .arg("stdin_eof_subprocess_helper")
        .env("INQUIRER_AI_MODE", "agent")
        .env("RUN_STDIN_EOF_HELPER", "1")
        // Remove fd overrides so it uses stdin/stdout
        .env_remove("INQUIRER_AI_FD_OUT")
        .env_remove("INQUIRER_AI_FD_IN")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .output()
        .expect("Failed to spawn subprocess");

    // Should exit with code 42 (our sentinel for PromptAborted)
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert_eq!(
        output.status.code(),
        Some(42),
        "Expected exit code 42 (PromptAborted). stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn stdin_eof_subprocess_helper() {
    if std::env::var("RUN_STDIN_EOF_HELPER").is_err() {
        return;
    }

    // stdin is piped but the parent immediately closes it (drops the handle
    // without writing), so the first read_line will get 0 bytes -> EOF.
    let payload = json!({
        "type": "confirm",
        "message": "test",
    });
    let _ = inquirer_ai::agent::agent_send(&payload);
    let result = inquirer_ai::agent::agent_receive();

    match result {
        Err(InquirerError::PromptAborted(_)) => std::process::exit(42),
        Err(e) => {
            eprintln!("Unexpected error: {e}");
            std::process::exit(1);
        }
        Ok(v) => {
            eprintln!("Unexpected success: {v}");
            std::process::exit(1);
        }
    }
}
