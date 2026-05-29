//! Cross-language consistency tests for coerce_bool and validate_number.
//!
//! These tests verify that Rust behaves correctly on edge cases found
//! through cross-language analysis with the Python and Go implementations.

use inquirer_ai::prompts::confirm::coerce_bool;
use inquirer_ai::prompts::number::{validate_number, NumberConfig};
use serde_json::json;

// =========================================================================
// coerce_bool: numeric edge cases
// =========================================================================

#[test]
fn coerce_bool_nan_is_false() {
    // JSON does not have NaN, so we test the string "NaN" and f64 NaN via Number
    // serde_json::json! does not support NaN directly, so test string form
    assert!(!coerce_bool(&json!("NaN")));
}

#[test]
fn coerce_bool_inf_is_false() {
    assert!(!coerce_bool(&json!("Infinity")));
}

#[test]
fn coerce_bool_neg_inf_is_false() {
    assert!(!coerce_bool(&json!("-Infinity")));
}

#[test]
fn coerce_bool_zero_float_is_false() {
    assert!(!coerce_bool(&json!(0.0)));
}

#[test]
fn coerce_bool_one_float_is_true() {
    assert!(coerce_bool(&json!(1.0)));
}

#[test]
fn coerce_bool_neg_one_float_is_true() {
    assert!(coerce_bool(&json!(-1.0)));
}

// =========================================================================
// coerce_bool: string edge cases
// =========================================================================

#[test]
fn coerce_bool_empty_string_is_false() {
    assert!(!coerce_bool(&json!("")));
}

#[test]
fn coerce_bool_yes_is_true() {
    assert!(coerce_bool(&json!("yes")));
}

#[test]
fn coerce_bool_no_is_false() {
    assert!(!coerce_bool(&json!("no")));
}

#[test]
fn coerce_bool_y_is_true() {
    assert!(coerce_bool(&json!("y")));
}

#[test]
fn coerce_bool_n_is_false() {
    assert!(!coerce_bool(&json!("n")));
}

#[test]
fn coerce_bool_true_string_is_true() {
    assert!(coerce_bool(&json!("true")));
}

#[test]
fn coerce_bool_false_string_is_false() {
    assert!(!coerce_bool(&json!("false")));
}

#[test]
fn coerce_bool_one_string_is_true() {
    assert!(coerce_bool(&json!("1")));
}

#[test]
fn coerce_bool_zero_string_is_false() {
    assert!(!coerce_bool(&json!("0")));
}

// =========================================================================
// coerce_bool: null and boolean
// =========================================================================

#[test]
fn coerce_bool_null_is_false() {
    assert!(!coerce_bool(&json!(null)));
}

#[test]
fn coerce_bool_true_is_true() {
    assert!(coerce_bool(&json!(true)));
}

#[test]
fn coerce_bool_false_is_false() {
    assert!(!coerce_bool(&json!(false)));
}

// =========================================================================
// coerce_bool: case insensitivity
// =========================================================================

#[test]
fn coerce_bool_yes_uppercase_is_true() {
    assert!(coerce_bool(&json!("YES")));
}

#[test]
fn coerce_bool_true_mixed_case_is_true() {
    assert!(coerce_bool(&json!("True")));
}

#[test]
fn coerce_bool_y_uppercase_is_true() {
    assert!(coerce_bool(&json!("Y")));
}

#[test]
fn coerce_bool_no_uppercase_is_false() {
    assert!(!coerce_bool(&json!("NO")));
}

#[test]
fn coerce_bool_false_mixed_case_is_false() {
    assert!(!coerce_bool(&json!("False")));
}

// =========================================================================
// validate_number: non-finite rejection
// =========================================================================

#[test]
fn validate_number_nan_string_rejected() {
    let config = NumberConfig::new("x");
    let result = validate_number(&json!("NaN"), &config);
    assert!(result.is_err(), "NaN string should be rejected");
}

#[test]
fn validate_number_inf_string_rejected() {
    let config = NumberConfig::new("x");
    let result = validate_number(&json!("Infinity"), &config);
    assert!(result.is_err(), "Infinity string should be rejected");
}

#[test]
fn validate_number_neg_inf_string_rejected() {
    let config = NumberConfig::new("x");
    let result = validate_number(&json!("-Infinity"), &config);
    assert!(result.is_err(), "-Infinity string should be rejected");
}

// =========================================================================
// validate_number: normal numbers
// =========================================================================

#[test]
fn validate_number_positive_integer() {
    let config = NumberConfig::new("x");
    assert_eq!(validate_number(&json!(42), &config).unwrap(), 42.0);
}

#[test]
fn validate_number_negative_integer() {
    let config = NumberConfig::new("x");
    assert_eq!(validate_number(&json!(-7), &config).unwrap(), -7.0);
}

#[test]
fn validate_number_zero() {
    let config = NumberConfig::new("x");
    assert_eq!(validate_number(&json!(0), &config).unwrap(), 0.0);
}

#[test]
fn validate_number_float() {
    let config = NumberConfig::new("x");
    let result = validate_number(&json!(1.234), &config).unwrap();
    assert!((result - 1.234).abs() < f64::EPSILON);
}

// =========================================================================
// validate_number: min/max bounds
// =========================================================================

#[test]
fn validate_number_at_min_boundary() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: Some(5.0),
        max: Some(10.0),
        step: None,
        float_allowed: true,
        keep_input: true,
    };
    assert_eq!(validate_number(&json!(5), &config).unwrap(), 5.0);
}

#[test]
fn validate_number_at_max_boundary() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: Some(5.0),
        max: Some(10.0),
        step: None,
        float_allowed: true,
        keep_input: true,
    };
    assert_eq!(validate_number(&json!(10), &config).unwrap(), 10.0);
}

#[test]
fn validate_number_below_min_rejected() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: Some(5.0),
        max: Some(10.0),
        step: None,
        float_allowed: true,
        keep_input: true,
    };
    assert!(validate_number(&json!(4), &config).is_err());
}

#[test]
fn validate_number_above_max_rejected() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: Some(5.0),
        max: Some(10.0),
        step: None,
        float_allowed: true,
        keep_input: true,
    };
    assert!(validate_number(&json!(11), &config).is_err());
}

// =========================================================================
// validate_number: float_allowed=false
// =========================================================================

#[test]
fn validate_number_float_not_allowed_whole_number_accepted() {
    // 3.0 should be accepted and truncated to 3
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: None,
        max: None,
        step: None,
        float_allowed: false,
        keep_input: true,
    };
    let result = validate_number(&json!(3.0), &config).unwrap();
    assert_eq!(result, 3.0);
}

#[test]
fn validate_number_float_not_allowed_fractional_rejected() {
    // 3.5 should be rejected
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: None,
        max: None,
        step: None,
        float_allowed: false,
        keep_input: true,
    };
    assert!(
        validate_number(&json!(3.5), &config).is_err(),
        "3.5 should be rejected when float_allowed=false"
    );
}

#[test]
fn validate_number_float_not_allowed_string_whole_accepted() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: None,
        max: None,
        step: None,
        float_allowed: false,
        keep_input: true,
    };
    let result = validate_number(&json!("3.0"), &config).unwrap();
    assert_eq!(result, 3.0);
}

#[test]
fn validate_number_float_not_allowed_string_fractional_rejected() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: None,
        max: None,
        step: None,
        float_allowed: false,
        keep_input: true,
    };
    assert!(
        validate_number(&json!("3.5"), &config).is_err(),
        "\"3.5\" should be rejected when float_allowed=false"
    );
}

// =========================================================================
// R2 — numeric-string grammar (accept/reject must match all 4 languages)
// =========================================================================

#[test]
fn number_grammar_accepts() {
    let config = NumberConfig::new("x");
    // "1e3" -> 1000
    assert_eq!(validate_number(&json!("1e3"), &config).unwrap(), 1000.0);
    // "  5  " -> 5 (whitespace trimmed)
    assert_eq!(validate_number(&json!("  5  "), &config).unwrap(), 5.0);
    // "3.5"
    assert!((validate_number(&json!("3.5"), &config).unwrap() - 3.5).abs() < f64::EPSILON);
    // "-2"
    assert_eq!(validate_number(&json!("-2"), &config).unwrap(), -2.0);
    // "1E-3" -> 0.001
    assert!((validate_number(&json!("1E-3"), &config).unwrap() - 0.001).abs() < f64::EPSILON);
    // "+5"
    assert_eq!(validate_number(&json!("+5"), &config).unwrap(), 5.0);
}

#[test]
fn number_grammar_rejects() {
    let config = NumberConfig::new("x");
    for bad in [
        "1_000", "3abc", "0x10", ".5", "5.", "", "+", "  ", "1.2.3", "e3",
    ] {
        assert!(
            validate_number(&json!(bad), &config).is_err(),
            "grammar should reject {bad:?}"
        );
    }
}
