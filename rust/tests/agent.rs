//! Tests for agent.rs — extract_answer and property-based tests.
//!
//! This file provides the first test coverage for the agent module.

use inquirer_ai::agent::extract_answer;
use inquirer_ai::prompts::confirm::coerce_bool;
use inquirer_ai::prompts::number::{validate_number, NumberConfig};
use proptest::prelude::*;
use serde_json::{json, Value};

// =========================================================================
// extract_answer: valid inputs
// =========================================================================

#[test]
fn extract_answer_string() {
    let resp = json!({"answer": "hello"});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!("hello"));
}

#[test]
fn extract_answer_number() {
    let resp = json!({"answer": 42});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(42));
}

#[test]
fn extract_answer_boolean() {
    let resp = json!({"answer": true});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(true));
}

#[test]
fn extract_answer_array() {
    let resp = json!({"answer": ["a", "b"]});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(["a", "b"]));
}

#[test]
fn extract_answer_null_value() {
    let resp = json!({"answer": null});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(null));
}

#[test]
fn extract_answer_nested_object() {
    let resp = json!({"answer": {"key": "value"}});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!({"key": "value"}));
}

#[test]
fn extract_answer_float() {
    let resp = json!({"answer": 1.234});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!(1.234));
}

// =========================================================================
// extract_answer: invalid inputs
// =========================================================================

#[test]
fn extract_answer_missing_answer_key() {
    let resp = json!({});
    let result = extract_answer(&resp);
    assert!(result.is_err(), "empty object should fail");
}

#[test]
fn extract_answer_wrong_key() {
    let resp = json!({"ans": "hello"});
    let result = extract_answer(&resp);
    assert!(result.is_err(), "wrong key name should fail");
}

#[test]
fn extract_answer_not_an_object_string() {
    let resp = json!("hello");
    let result = extract_answer(&resp);
    assert!(result.is_err(), "plain string should fail");
}

#[test]
fn extract_answer_not_an_object_number() {
    let resp = json!(42);
    let result = extract_answer(&resp);
    assert!(result.is_err(), "plain number should fail");
}

#[test]
fn extract_answer_not_an_object_array() {
    let resp = json!([1, 2, 3]);
    let result = extract_answer(&resp);
    assert!(result.is_err(), "array should fail");
}

#[test]
fn extract_answer_not_an_object_bool() {
    let resp = json!(true);
    let result = extract_answer(&resp);
    assert!(result.is_err(), "plain boolean should fail");
}

#[test]
fn extract_answer_not_an_object_null() {
    let resp = json!(null);
    let result = extract_answer(&resp);
    assert!(result.is_err(), "null should fail");
}

#[test]
fn extract_answer_extra_keys_still_works() {
    // Having extra keys alongside "answer" should still succeed
    let resp = json!({"answer": "hello", "extra": "ignored"});
    let result = extract_answer(&resp).unwrap();
    assert_eq!(result, json!("hello"));
}

// =========================================================================
// Property-based tests
// =========================================================================

/// Generate an arbitrary JSON value for proptest.
fn arb_json_value() -> impl Strategy<Value = Value> {
    prop_oneof![
        Just(json!(null)),
        any::<bool>().prop_map(|b| json!(b)),
        any::<i64>().prop_map(|n| json!(n)),
        any::<f64>()
            .prop_filter("must be finite", |f| f.is_finite())
            .prop_map(|f| json!(f)),
        "[a-zA-Z0-9 ]{0,50}".prop_map(|s| json!(s)),
    ]
}

proptest! {
    /// Any valid JSON value wrapped in {"answer": v} should be extractable.
    #[test]
    fn extract_answer_any_value(val in arb_json_value()) {
        let resp = json!({"answer": val.clone()});
        let result = extract_answer(&resp).unwrap();
        prop_assert_eq!(result, val);
    }

    /// coerce_bool should never panic for any JSON value.
    #[test]
    fn coerce_bool_never_panics(val in prop_oneof![
        any::<bool>().prop_map(|b| json!(b)),
        "[a-zA-Z0-9]{0,20}".prop_map(|s| json!(s)),
        any::<i64>().prop_map(|n| json!(n)),
        Just(json!(null)),
        any::<f64>()
            .prop_filter("must be finite", |f| f.is_finite())
            .prop_map(|f| json!(f)),
    ]) {
        let result = coerce_bool(&val);
        // Just verify it returns a bool (which it must, by type)
        let _ = result;
    }

    /// validate_number with a valid result always respects [min, max].
    #[test]
    fn validate_number_result_within_bounds(
        value in -1000i64..1000i64,
        min_val in -500i64..0i64,
        max_val in 1i64..500i64,
    ) {
        let config = NumberConfig {
            message: "x".into(),
            default: None,
            min: Some(min_val as f64),
            max: Some(max_val as f64),
            step: None,
            float_allowed: true,
        };
        if let Ok(n) = validate_number(&json!(value), &config) {
            prop_assert!(n >= min_val as f64, "result {} < min {}", n, min_val);
            prop_assert!(n <= max_val as f64, "result {} > max {}", n, max_val);
        }
    }

    /// validate_number with float_allowed=false always returns an integer.
    #[test]
    fn validate_number_no_float_is_integer(value in -1000i64..1000i64) {
        let config = NumberConfig {
            message: "x".into(),
            default: None,
            min: None,
            max: None,
            step: None,
            float_allowed: false,
        };
        let result = validate_number(&json!(value), &config).unwrap();
        prop_assert_eq!(result.trunc(), result, "result should be an integer");
    }

    /// validate_number with float_allowed=false and float inputs:
    /// if the value has a fractional part, it should be rejected.
    #[test]
    fn validate_number_no_float_rejects_fractions(
        whole in -100i64..100i64,
        frac in 1u32..100u32,
    ) {
        let val = whole as f64 + (frac as f64 / 100.0);
        // Only test values with actual fractional parts
        if val.fract() != 0.0 {
            let config = NumberConfig {
                message: "x".into(),
                default: None,
                min: None,
                max: None,
                step: None,
                float_allowed: false,
            };
            // Pass as string to avoid serde_json normalizing e.g. 1.0 to 1
            let val_str = format!("{val}");
            let result = validate_number(&json!(val_str), &config);
            prop_assert!(result.is_err(), "fractional value {val} should be rejected");
        }
    }
}
