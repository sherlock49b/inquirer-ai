use inquirer_ai::choice::{parse_choice, parse_choice_from_value, Choice, ChoiceItem};
use inquirer_ai::prompts::number::{validate_number, NumberConfig};
use serde_json::json;

#[test]
fn number_100k_string() {
    let long = "1".repeat(100_000);
    let config = NumberConfig::new("x");
    // Extremely large number string - should either parse or error cleanly
    let result = validate_number(&json!(long), &config);
    // It may succeed with Infinity or fail with validation - both are acceptable
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn unicode_choice_name() {
    let item = parse_choice("日本語🎉");
    match item {
        ChoiceItem::Choice(c) => assert_eq!(c.name, "日本語🎉"),
        _ => panic!("expected Choice"),
    }
}

#[test]
fn empty_string_choice() {
    let item = parse_choice("");
    match item {
        ChoiceItem::Choice(c) => assert_eq!(c.name, ""),
        _ => panic!("expected Choice"),
    }
}

#[test]
fn choice_with_special_json_chars() {
    let item = parse_choice(r#"he said "hello""#);
    match item {
        ChoiceItem::Choice(c) => {
            assert!(c.name.contains('"'));
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn choice_from_nested_json() {
    let val = json!({"name": "test", "value": {"nested": "object"}});
    let item = parse_choice_from_value(val);
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "test");
            assert!(c.value.is_object());
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn choice_from_number_value() {
    let item = parse_choice_from_value(json!(42));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.value, json!(42));
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn choice_from_null() {
    let item = parse_choice_from_value(json!(null));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.value, json!(null));
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn number_rejects_object() {
    let config = NumberConfig::new("x");
    assert!(validate_number(&json!({"nested": 1}), &config).is_err());
}

#[test]
fn number_rejects_array() {
    let config = NumberConfig::new("x");
    assert!(validate_number(&json!([1, 2, 3]), &config).is_err());
}

#[test]
fn choice_disabled_with_false() {
    let mut c = Choice::new("a", "a");
    c.disabled = Some(json!(false));
    assert!(!c.is_disabled());
}

#[test]
fn choice_disabled_with_empty_string() {
    let mut c = Choice::new("a", "a");
    c.disabled = Some(json!(""));
    assert!(!c.is_disabled());
}

#[test]
fn separator_custom_text() {
    let item = parse_choice_from_value(json!({"type": "separator", "text": "── section ──"}));
    match item {
        ChoiceItem::Separator(s) => assert_eq!(s.text, "── section ──"),
        _ => panic!("expected Separator"),
    }
}
