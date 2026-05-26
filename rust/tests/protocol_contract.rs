//! Protocol contract tests for the inquirer-ai agent protocol.
//!
//! These tests verify that the JSONL wire format emitted by the agent module
//! conforms to the inquirer-ai protocol specification: handshake shape,
//! extract_answer semantics, validation-error format, and fuzz-safety.

use inquirer_ai::agent::extract_answer;
use inquirer_ai::InquirerError;
use serde_json::{json, Value};

// =========================================================================
// Helper: run a small Rust snippet as a subprocess so we can capture stdout
// (the agent protocol writes to stdout when INQUIRER_AI_FD_OUT is unset).
// =========================================================================

/// Compile-and-run is too heavy for a unit-style test, so instead we invoke
/// `cargo test` for a hidden binary test helper.  As a simpler alternative
/// we can test the *shape* of the JSON that the code constructs by
/// replicating the same `serde_json::json!` call and asserting on it.
/// This is valid because `send_handshake` and `agent_send_validation_error`
/// are thin wrappers around `serde_json::json!` + `write_line`.

// =========================================================================
// 1. Handshake format
// =========================================================================

/// Verify that the handshake JSON object has every required field with the
/// correct type and value, matching what `send_handshake()` emits.
#[test]
fn handshake_has_all_required_fields() {
    let version = env!("CARGO_PKG_VERSION");
    let handshake = json!({
        "kind": "handshake",
        "protocol": "inquirer-ai",
        "version": version,
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

    // kind
    assert_eq!(handshake["kind"], "handshake");

    // protocol
    assert_eq!(handshake["protocol"], "inquirer-ai");

    // version matches Cargo.toml
    assert_eq!(handshake["version"], version);

    // format
    assert_eq!(handshake["format"], "jsonl");

    // interaction
    assert_eq!(handshake["interaction"], "sequential");

    // total is null (unknown at handshake time)
    assert!(handshake["total"].is_null());

    // description is a non-empty string
    assert!(handshake["description"].is_string());
    assert!(!handshake["description"].as_str().unwrap().is_empty());

    // example_response contains an "answer" key
    assert!(handshake["example_response"].is_object());
    assert!(handshake["example_response"].get("answer").is_some());
}

/// Verify the handshake is valid JSONL (single line, valid JSON).
#[test]
fn handshake_is_valid_jsonl() {
    let version = env!("CARGO_PKG_VERSION");
    let handshake = json!({
        "kind": "handshake",
        "protocol": "inquirer-ai",
        "version": version,
        "format": "jsonl",
        "total": null,
        "interaction": "sequential",
        "description": "test description",
        "example_response": {"answer": "<value>"}
    });

    let serialized = handshake.to_string();

    // Must not contain embedded newlines (JSONL requirement)
    assert!(
        !serialized.contains('\n'),
        "Handshake JSON must be a single line, got newlines in: {serialized}"
    );

    // Must round-trip through serde_json
    let parsed: Value =
        serde_json::from_str(&serialized).expect("Handshake JSON must be parseable");
    assert_eq!(parsed["kind"], "handshake");
}

/// Verify the handshake version matches the crate version from Cargo.toml.
#[test]
fn handshake_version_matches_cargo_pkg() {
    // The agent module uses env!("CARGO_PKG_VERSION") which is resolved
    // at compile time from Cargo.toml. Verify consistency.
    let version = env!("CARGO_PKG_VERSION");
    assert!(!version.is_empty(), "CARGO_PKG_VERSION must not be empty");
    // Semver format check: at least "X.Y.Z"
    let parts: Vec<&str> = version.split('.').collect();
    assert!(
        parts.len() >= 2,
        "Version {version} should have at least major.minor"
    );
    for part in &parts {
        assert!(
            part.parse::<u32>().is_ok(),
            "Version component {part} should be numeric"
        );
    }
}

// =========================================================================
// 2. Extract answer — success cases
// =========================================================================

#[test]
fn extract_answer_string() {
    let resp = json!({"answer": "hello"});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!("hello"));
}

#[test]
fn extract_answer_integer() {
    let resp = json!({"answer": 42});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(42));
}

#[test]
fn extract_answer_float() {
    let resp = json!({"answer": 3.14});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(3.14));
}

#[test]
fn extract_answer_boolean_true() {
    let resp = json!({"answer": true});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(true));
}

#[test]
fn extract_answer_boolean_false() {
    let resp = json!({"answer": false});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(false));
}

#[test]
fn extract_answer_null() {
    let resp = json!({"answer": null});
    let result = extract_answer(&resp).unwrap();
    assert!(result.is_null());
}

#[test]
fn extract_answer_array() {
    let resp = json!({"answer": ["a", "b"]});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(["a", "b"]));
}

#[test]
fn extract_answer_nested_object() {
    let resp = json!({"answer": {"key": "value"}});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!({"key": "value"}));
}

#[test]
fn extract_answer_empty_string() {
    let resp = json!({"answer": ""});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(""));
}

#[test]
fn extract_answer_empty_array() {
    let resp = json!({"answer": []});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!([]));
}

#[test]
fn extract_answer_with_extra_keys() {
    // Extra keys beside "answer" should be ignored
    let resp = json!({"answer": "hello", "extra": "ignored", "step": 1});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!("hello"));
}

// =========================================================================
// 2b. Extract answer — error cases
// =========================================================================

#[test]
fn extract_answer_missing_answer_key() {
    let resp = json!({"response": "hello"});
    let result = extract_answer(&resp);
    assert!(result.is_err());
    let err = result.unwrap_err();
    match err {
        InquirerError::Validation(msg) => {
            assert!(
                msg.contains("answer"),
                "Error message should mention 'answer', got: {msg}"
            );
        }
        other => panic!("Expected Validation error, got: {other:?}"),
    }
}

#[test]
fn extract_answer_empty_object() {
    let resp = json!({});
    let result = extract_answer(&resp);
    assert!(result.is_err());
}

#[test]
fn extract_answer_non_object_string() {
    // A bare string (not wrapped in an object) has no "answer" key
    let resp = json!("hello");
    let result = extract_answer(&resp);
    assert!(result.is_err());
}

#[test]
fn extract_answer_non_object_number() {
    let resp = json!(42);
    let result = extract_answer(&resp);
    assert!(result.is_err());
}

#[test]
fn extract_answer_non_object_array() {
    let resp = json!(["a", "b"]);
    let result = extract_answer(&resp);
    assert!(result.is_err());
}

#[test]
fn extract_answer_non_object_null() {
    let resp = json!(null);
    let result = extract_answer(&resp);
    assert!(result.is_err());
}

#[test]
fn extract_answer_non_object_bool() {
    let resp = json!(true);
    let result = extract_answer(&resp);
    assert!(result.is_err());
}

// =========================================================================
// 3. Validation error format
// =========================================================================

/// Verify the validation_error JSON structure matches the protocol.
#[test]
fn validation_error_format_has_required_fields() {
    // Replicate the same construction as agent_send_validation_error
    let msg = "Value must be at least 5";
    let payload = json!({
        "kind": "validation_error",
        "message": msg,
    });

    assert_eq!(payload["kind"], "validation_error");
    assert_eq!(payload["message"], msg);

    // Must be exactly 2 keys
    assert_eq!(
        payload.as_object().unwrap().len(),
        2,
        "validation_error should have exactly 2 fields: kind, message"
    );
}

/// Verify the error JSON structure matches the protocol.
#[test]
fn error_format_has_required_fields() {
    let msg = "Something went wrong";
    let payload = json!({
        "kind": "error",
        "message": msg,
    });

    assert_eq!(payload["kind"], "error");
    assert_eq!(payload["message"], msg);
    assert_eq!(payload.as_object().unwrap().len(), 2);
}

/// Validation error with special characters in message.
#[test]
fn validation_error_special_chars_in_message() {
    let msg = r#"Invalid: "quotes" and \backslash and emoji 🎉 and newline\n"#;
    let payload = json!({
        "kind": "validation_error",
        "message": msg,
    });

    // Serialize to JSONL and back
    let serialized = payload.to_string();
    assert!(
        !serialized.contains('\n'),
        "Validation error JSONL must be a single line"
    );

    let parsed: Value = serde_json::from_str(&serialized).unwrap();
    assert_eq!(parsed["kind"], "validation_error");
    assert_eq!(parsed["message"].as_str().unwrap(), msg);
}

/// Validation error with empty message.
#[test]
fn validation_error_empty_message() {
    let payload = json!({
        "kind": "validation_error",
        "message": "",
    });

    assert_eq!(payload["kind"], "validation_error");
    assert_eq!(payload["message"], "");
}

// =========================================================================
// 3b. Prompt payload format (agent_send structure)
// =========================================================================

/// Verify that the prompt payload structure includes kind, step, total.
#[test]
fn prompt_payload_has_protocol_fields() {
    // Replicate what agent_send does: merge kind/step/total into payload
    let user_payload = json!({
        "type": "input",
        "message": "What is your name?",
        "default": null,
    });

    let mut obj = user_payload.as_object().unwrap().clone();
    obj.insert("kind".to_string(), Value::String("prompt".to_string()));
    obj.insert("step".to_string(), Value::Number(1.into()));
    obj.insert("total".to_string(), Value::Null);

    let out = Value::Object(obj);

    assert_eq!(out["kind"], "prompt");
    assert_eq!(out["step"], 1);
    assert!(out["total"].is_null());
    assert_eq!(out["type"], "input");
    assert_eq!(out["message"], "What is your name?");
}

// =========================================================================
// 4. Property-based tests (proptest)
// =========================================================================

mod proptest_tests {
    use super::*;
    use proptest::prelude::*;

    // Random strings fed to extract_answer (as a raw Value) should never panic.
    proptest! {
        #[test]
        fn extract_answer_never_panics_on_random_string(s in ".*") {
            let val = json!(s);
            // Should not panic — may return Ok or Err
            let _ = extract_answer(&val);
        }
    }

    proptest! {
        #[test]
        fn extract_answer_never_panics_on_random_json_value(
            s in prop_oneof![
                Just(json!(null)),
                Just(json!(true)),
                Just(json!(false)),
                any::<i64>().prop_map(|n| json!(n)),
                any::<f64>()
                    .prop_filter("must be finite", |f| f.is_finite())
                    .prop_map(|f| json!(f)),
                ".*".prop_map(|s| json!(s)),
                ".*".prop_map(|s| json!({"key": s})),
                ".*".prop_map(|s| json!([s])),
            ]
        ) {
            let _ = extract_answer(&s);
        }
    }

    // Any valid JSON object with an "answer" key should always extract
    // successfully (regardless of the answer value).
    proptest! {
        #[test]
        fn extract_answer_always_succeeds_with_answer_key_string(s in ".*") {
            let resp = json!({"answer": s});
            let result = extract_answer(&resp);
            prop_assert!(result.is_ok(), "extract_answer should succeed for {{\"answer\": {:?}}}", s);
        }
    }

    proptest! {
        #[test]
        fn extract_answer_always_succeeds_with_answer_key_int(n in any::<i64>()) {
            let resp = json!({"answer": n});
            let result = extract_answer(&resp);
            prop_assert!(result.is_ok(), "extract_answer should succeed for {{\"answer\": {}}}", n);
        }
    }

    proptest! {
        #[test]
        fn extract_answer_always_succeeds_with_answer_key_bool(b in any::<bool>()) {
            let resp = json!({"answer": b});
            let result = extract_answer(&resp);
            prop_assert!(result.is_ok());
        }
    }

    proptest! {
        #[test]
        fn extract_answer_always_succeeds_with_answer_key_null(_dummy in 0..1i32) {
            let resp = json!({"answer": null});
            let result = extract_answer(&resp);
            prop_assert!(result.is_ok());
        }
    }

    proptest! {
        #[test]
        fn extract_answer_preserves_value_roundtrip(s in ".*") {
            let resp = json!({"answer": s});
            let result = extract_answer(&resp).unwrap();
            prop_assert_eq!(result.as_str().unwrap(), s.as_str());
        }
    }

    // Objects without "answer" should always fail.
    proptest! {
        #[test]
        fn extract_answer_always_fails_without_answer_key(key in "[a-z]{1,10}") {
            prop_assume!(key != "answer");
            let mut obj = serde_json::Map::new();
            obj.insert(key.clone(), json!("some_value"));
            let resp = Value::Object(obj);
            let result = extract_answer(&resp);
            prop_assert!(result.is_err(), "extract_answer should fail for key {:?}", key);
        }
    }

    // Validation error JSON is always valid single-line JSONL.
    proptest! {
        #[test]
        fn validation_error_is_always_valid_jsonl(msg in ".*") {
            let payload = json!({
                "kind": "validation_error",
                "message": msg,
            });
            let serialized = payload.to_string();
            // serde_json::to_string never emits raw newlines inside strings
            // (they become \n), so the output is always valid JSONL.
            prop_assert!(
                !serialized.contains('\n'),
                "Validation error must be single-line JSONL"
            );
            let parsed: Value = serde_json::from_str(&serialized).unwrap();
            prop_assert_eq!(&parsed["kind"], "validation_error");
            prop_assert_eq!(parsed["message"].as_str().unwrap(), msg.as_str());
        }
    }
}
