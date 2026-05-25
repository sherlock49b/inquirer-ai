use inquirer_ai::choice::Choice;
use inquirer_ai::prompts::confirm::coerce_bool;
use inquirer_ai::prompts::expand::{validate_expand, ExpandChoice};
use inquirer_ai::prompts::number::{validate_number, NumberConfig};
use inquirer_ai::prompts::rawlist::validate_rawlist;
use serde_json::json;

#[test]
fn coerce_bool_truthy() {
    assert!(coerce_bool(&json!(true)));
    assert!(coerce_bool(&json!("y")));
    assert!(coerce_bool(&json!("yes")));
    assert!(coerce_bool(&json!("YES")));
    assert!(coerce_bool(&json!("true")));
    assert!(coerce_bool(&json!("1")));
    assert!(coerce_bool(&json!(1)));
}

#[test]
fn coerce_bool_falsy() {
    assert!(!coerce_bool(&json!(false)));
    assert!(!coerce_bool(&json!("n")));
    assert!(!coerce_bool(&json!("no")));
    assert!(!coerce_bool(&json!("false")));
    assert!(!coerce_bool(&json!("0")));
    assert!(!coerce_bool(&json!(null)));
    assert!(!coerce_bool(&json!("anything")));
}

#[test]
fn number_validates_bounds() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: Some(10.0),
        max: Some(100.0),
        step: None,
        float_allowed: true,
        keep_input: true,
    };

    assert!(validate_number(&json!(50), &config).is_ok());
    assert!(validate_number(&json!(10), &config).is_ok());
    assert!(validate_number(&json!(100), &config).is_ok());
    assert!(validate_number(&json!(5), &config).is_err());
    assert!(validate_number(&json!(101), &config).is_err());
}

#[test]
fn number_rejects_non_finite() {
    let config = NumberConfig::new("x");
    assert!(validate_number(&json!("NaN"), &config).is_err());
    assert!(validate_number(&json!("Infinity"), &config).is_err());
    assert!(validate_number(&json!("-Infinity"), &config).is_err());
}

#[test]
fn number_rejects_float_when_not_allowed() {
    let config = NumberConfig {
        message: "x".into(),
        default: None,
        min: None,
        max: None,
        step: None,
        float_allowed: false,
        keep_input: true,
    };

    assert!(validate_number(&json!(1.234), &config).is_err());
    let result = validate_number(&json!(5.0), &config).unwrap();
    assert_eq!(result, 5.0);
}

#[test]
fn number_uses_default() {
    let config = NumberConfig {
        message: "x".into(),
        default: Some(42.0),
        min: None,
        max: None,
        step: None,
        float_allowed: true,
        keep_input: true,
    };
    assert_eq!(validate_number(&json!(null), &config).unwrap(), 42.0);
}

#[test]
fn number_rejects_boolean() {
    let config = NumberConfig::new("x");
    assert!(validate_number(&json!(true), &config).is_err());
}

#[test]
fn number_parses_string() {
    let config = NumberConfig::new("x");
    assert_eq!(validate_number(&json!("42"), &config).unwrap(), 42.0);
    assert!((validate_number(&json!("1.234"), &config).unwrap() - 1.234).abs() < f64::EPSILON);
}

#[test]
fn number_rejects_invalid_string() {
    let config = NumberConfig::new("x");
    assert!(validate_number(&json!("abc"), &config).is_err());
}

#[test]
fn rawlist_accepts_index() {
    let choices = vec![
        Choice::new("3.13", json!("3.13")),
        Choice::new("3.12", json!("3.12")),
    ];
    assert_eq!(
        validate_rawlist(&json!(1), &choices).unwrap(),
        json!("3.13")
    );
    assert_eq!(
        validate_rawlist(&json!(2), &choices).unwrap(),
        json!("3.12")
    );
}

#[test]
fn rawlist_accepts_by_value() {
    let choices = vec![Choice::new("3.13", json!("3.13"))];
    assert_eq!(
        validate_rawlist(&json!("3.13"), &choices).unwrap(),
        json!("3.13")
    );
}

#[test]
fn rawlist_rejects_invalid() {
    let choices = vec![Choice::new("a", json!("a"))];
    assert!(validate_rawlist(&json!(99), &choices).is_err());
    assert!(validate_rawlist(&json!("nope"), &choices).is_err());
}

#[test]
fn expand_accepts_key() {
    let choices = vec![
        ExpandChoice {
            key: "y".into(),
            name: "Overwrite".into(),
            value: json!("overwrite"),
        },
        ExpandChoice {
            key: "n".into(),
            name: "Skip".into(),
            value: json!("skip"),
        },
    ];
    assert_eq!(
        validate_expand(&json!("y"), &choices).unwrap(),
        json!("overwrite")
    );
    assert_eq!(
        validate_expand(&json!("n"), &choices).unwrap(),
        json!("skip")
    );
}

#[test]
fn expand_rejects_invalid() {
    let choices = vec![ExpandChoice {
        key: "y".into(),
        name: "Yes".into(),
        value: json!("yes"),
    }];
    assert!(validate_expand(&json!("z"), &choices).is_err());
}
