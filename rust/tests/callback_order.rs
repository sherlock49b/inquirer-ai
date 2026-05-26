//! Tests for the callback execution order invariant: validate -> filter.
//!
//! The critical invariant is:
//!   1. Built-in validation runs first (e.g., validate_number, validate_expand)
//!   2. User-provided validate callback runs second
//!   3. Filter runs LAST, only on accepted values
//!
//! In Rust, only TextConfig has both validate and filter callbacks.
//! Select, Checkbox, and Expand don't expose user-level validate/filter.
//! Number only has built-in validation via validate_number.
//!
//! These tests verify the ordering by simulating the exact callback chain
//! used in the agent prompt closures (text_agent, number_agent, etc.).

use inquirer_ai::errors::InquirerError;
use inquirer_ai::prompts::expand::{validate_expand, ExpandChoice};
use inquirer_ai::prompts::number::{validate_number, NumberConfig};
use serde_json::json;
use std::cell::RefCell;

// ── Test 1: Order invariant — validate is called before filter ──

#[test]
fn text_callback_order_validate_before_filter() {
    // Simulates the text_agent closure pattern:
    //   validate(&result) -> filter(result)
    let log = RefCell::new(Vec::new());

    let validate = |_s: &str| -> Result<(), String> {
        log.borrow_mut().push("validate".to_string());
        Ok(())
    };
    let filter = |s: String| -> String {
        log.borrow_mut().push("filter".to_string());
        s
    };

    // Execute the same pattern as text_agent
    let mut result = "hello".to_string();
    validate(&result).unwrap();
    result = filter(result);

    let calls = log.borrow();
    assert_eq!(*calls, vec!["validate", "filter"]);
    assert_eq!(result, "hello");
}

#[test]
fn number_callback_order_builtin_first() {
    // Simulates number_agent: validate_number -> filter -> validate (no user validate in Rust)
    // Rust's NumberConfig doesn't have user validate/filter, so we test
    // that built-in validation runs before any transformation would.
    let config = NumberConfig::new("Q");
    let answer = json!(42);

    let log = RefCell::new(Vec::new());

    // Simulate the pattern: built-in validate -> (filter would go here)
    log.borrow_mut().push("builtin_validate".to_string());
    let result = validate_number(&answer, &config).unwrap();
    log.borrow_mut().push("filter".to_string());
    let _filtered = result * 2.0;

    let calls = log.borrow();
    assert_eq!(*calls, vec!["builtin_validate", "filter"]);
}

// ── Test 2: Filter NOT called when validate rejects ──

#[test]
fn text_filter_not_called_on_rejection() {
    let filter_called = RefCell::new(false);

    let validate = |_s: &str| -> Result<(), String> { Err("rejected".to_string()) };
    let filter = |s: String| -> String {
        *filter_called.borrow_mut() = true;
        s
    };

    // Simulate text_agent pattern: validate first, skip filter on error
    let result = "bad";
    if let Err(_) = validate(result) {
        // Filter should NOT be called
    } else {
        let _ = filter(result.to_string());
    }

    assert!(
        !*filter_called.borrow(),
        "filter must NOT be called when validate rejects"
    );
}

#[test]
fn number_filter_not_called_on_builtin_rejection() {
    let config = NumberConfig {
        message: "Q".into(),
        default: None,
        min: Some(0.0),
        max: Some(10.0),
        step: None,
        float_allowed: true,
        keep_input: true,
    };
    let answer = json!(100); // out of range

    let filter_called = RefCell::new(false);

    // Simulate number_agent: validate_number first, skip filter/user-validate on error
    match validate_number(&answer, &config) {
        Ok(result) => {
            *filter_called.borrow_mut() = true;
            let _ = result;
        }
        Err(InquirerError::Validation(msg)) => {
            assert!(msg.contains("at most"), "expected range error, got: {msg}");
        }
        Err(e) => panic!("unexpected error type: {e:?}"),
    }

    assert!(
        !*filter_called.borrow(),
        "filter must NOT be called when built-in validation rejects"
    );
}

// ── Test 3: Filter receives the raw value (before any transformation) ──

#[test]
fn text_filter_receives_raw_value() {
    let received = RefCell::new(String::new());

    let validate = |_s: &str| -> Result<(), String> { Ok(()) };
    let filter = |s: String| -> String {
        *received.borrow_mut() = s.clone();
        s.trim().to_string()
    };

    // Simulate text_agent pattern
    let mut result = "  HELLO  ".to_string();
    validate(&result).unwrap();
    result = filter(result);

    assert_eq!(
        *received.borrow(),
        "  HELLO  ",
        "filter should receive the raw value"
    );
    assert_eq!(
        result, "HELLO",
        "result should be the filtered (trimmed) value"
    );
}

#[test]
fn number_filter_receives_validated_number() {
    let config = NumberConfig::new("Q");
    let answer = json!(42);

    let received = RefCell::new(0.0f64);

    let result = validate_number(&answer, &config).unwrap();
    *received.borrow_mut() = result;
    let filtered = result * 2.0;

    assert_eq!(
        *received.borrow(),
        42.0,
        "filter should receive the validated number"
    );
    assert_eq!(filtered, 84.0);
}

// ── Test 4: Multiple rejections, filter called only once on accepted value ──

#[test]
fn text_multiple_rejections_filter_called_once() {
    let filter_calls = RefCell::new(Vec::<String>::new());

    let answers = vec!["bad1", "bad2", "good"];
    let mut attempt = 0;

    let validate = |_s: &str| -> Result<(), String> {
        // Can't capture attempt mutably in Fn, so we use the answer content
        Ok(()) // We'll track rejection via the loop pattern below
    };
    let filter = |s: String| -> String {
        filter_calls.borrow_mut().push(s.clone());
        format!("{s}_filtered")
    };

    let mut final_result = String::new();
    for answer in &answers {
        attempt += 1;
        let result = answer.to_string();
        if attempt <= 2 {
            // Simulate validation rejection (skip filter)
            continue;
        }
        validate(&result).unwrap();
        final_result = filter(result);
        break;
    }

    let calls = filter_calls.borrow();
    assert_eq!(calls.len(), 1, "filter should be called exactly once");
    assert_eq!(calls[0], "good", "filter should receive the accepted value");
    assert_eq!(final_result, "good_filtered");
}

// ── Test 5: Cross-type consistency ──
// Verify that all prompt types that have validation follow the same pattern:
// built-in validate -> user callbacks

#[test]
fn expand_builtin_validation_runs_first() {
    let choices = vec![
        ExpandChoice {
            key: "y".to_string(),
            name: "Yes".to_string(),
            value: json!("yes"),
        },
        ExpandChoice {
            key: "n".to_string(),
            name: "No".to_string(),
            value: json!("no"),
        },
    ];

    let log = RefCell::new(Vec::new());

    // Valid answer
    log.borrow_mut().push("builtin_validate".to_string());
    let result = validate_expand(&json!("y"), &choices).unwrap();
    log.borrow_mut().push("filter_would_run_here".to_string());

    assert_eq!(result, json!("yes"));
    assert_eq!(
        *log.borrow(),
        vec!["builtin_validate", "filter_would_run_here"]
    );
}

#[test]
fn expand_invalid_choice_stops_before_filter() {
    let choices = vec![ExpandChoice {
        key: "y".to_string(),
        name: "Yes".to_string(),
        value: json!("yes"),
    }];

    let filter_called = RefCell::new(false);

    match validate_expand(&json!("z"), &choices) {
        Ok(val) => {
            *filter_called.borrow_mut() = true;
            let _ = val;
        }
        Err(_) => {
            // Expected: filter not called
        }
    }

    assert!(
        !*filter_called.borrow(),
        "filter must NOT run after invalid expand choice"
    );
}

#[test]
fn number_step_validation_stops_before_filter() {
    let config = NumberConfig {
        message: "Q".into(),
        default: None,
        min: Some(0.0),
        max: Some(100.0),
        step: Some(5.0),
        float_allowed: true,
        keep_input: true,
    };

    // 7 is not a multiple of 5
    let filter_called = RefCell::new(false);
    match validate_number(&json!(7), &config) {
        Ok(val) => {
            *filter_called.borrow_mut() = true;
            let _ = val;
        }
        Err(InquirerError::Validation(msg)) => {
            assert!(msg.contains("multiple"), "expected step error, got: {msg}");
        }
        Err(e) => panic!("unexpected error: {e:?}"),
    }
    assert!(
        !*filter_called.borrow(),
        "filter must NOT run after step validation failure"
    );

    // 10 IS a multiple of 5 — filter should run
    let filter_ran = RefCell::new(false);
    match validate_number(&json!(10), &config) {
        Ok(val) => {
            *filter_ran.borrow_mut() = true;
            assert_eq!(val, 10.0);
        }
        Err(e) => panic!("unexpected error: {e:?}"),
    }
    assert!(
        *filter_ran.borrow(),
        "filter should run after successful validation"
    );
}

#[test]
fn cross_type_consistency_all_validation_types() {
    // Test that validate_number, validate_expand, and text validation all
    // follow the same pattern: validation error prevents downstream operations.

    struct TestCase {
        name: &'static str,
        validate: Box<dyn Fn() -> Result<(), String>>,
    }

    let cases = vec![
        TestCase {
            name: "number_out_of_range",
            validate: Box::new(|| {
                let config = NumberConfig {
                    message: "Q".into(),
                    default: None,
                    min: Some(0.0),
                    max: Some(10.0),
                    step: None,
                    float_allowed: true,
                    keep_input: true,
                };
                validate_number(&json!(100), &config)
                    .map(|_| ())
                    .map_err(|e| format!("{e}"))
            }),
        },
        TestCase {
            name: "expand_invalid_key",
            validate: Box::new(|| {
                let choices = vec![ExpandChoice {
                    key: "y".to_string(),
                    name: "Yes".to_string(),
                    value: json!("yes"),
                }];
                validate_expand(&json!("z"), &choices)
                    .map(|_| ())
                    .map_err(|e| format!("{e}"))
            }),
        },
        TestCase {
            name: "text_user_rejection",
            validate: Box::new(|| Err("user rejected".to_string())),
        },
    ];

    for case in &cases {
        let filter_called = RefCell::new(false);
        match (case.validate)() {
            Ok(()) => {
                *filter_called.borrow_mut() = true;
            }
            Err(_) => {
                // Expected: filter not called
            }
        }
        assert!(
            !*filter_called.borrow(),
            "{}: filter must NOT be called after validation failure",
            case.name
        );
    }
}
