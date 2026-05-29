use inquirer_ai::choice::{parse_choice, parse_choice_from_value, Choice, ChoiceItem, Separator};
use serde_json::{json, Value};

#[test]
fn parse_string_choice() {
    let item = parse_choice("hello");
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "hello");
            assert_eq!(c.value, Value::String("hello".into()));
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn parse_value_string() {
    let item = parse_choice_from_value(Value::String("test".into()));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "test");
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn parse_value_separator() {
    let item = parse_choice_from_value(json!({"type": "separator", "text": "---"}));
    match item {
        ChoiceItem::Separator(s) => {
            assert_eq!(s.text, "---");
        }
        _ => panic!("expected Separator"),
    }
}

#[test]
fn parse_value_choice_object() {
    let item = parse_choice_from_value(json!({
        "name": "Go",
        "value": "go",
        "description": "Systems language"
    }));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "Go");
            assert_eq!(c.value, json!("go"));
            assert_eq!(c.description, Some("Systems language".into()));
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn parse_value_choice_missing_value_defaults_to_name() {
    // R4: a choice object without a `value` defaults value := name (it must
    // NOT stringify the whole object).
    let item = parse_choice_from_value(json!({"name": "Deploy"}));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "Deploy");
            assert_eq!(c.value, json!("Deploy"));
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn parse_value_choice_preserves_disabled_and_typed_value() {
    let item = parse_choice_from_value(json!({
        "name": "Forty-two",
        "value": 42,
        "disabled": "nope"
    }));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "Forty-two");
            assert_eq!(c.value, json!(42));
            assert!(c.is_disabled());
            assert_eq!(c.disabled_reason(), Some("nope"));
        }
        _ => panic!("expected Choice"),
    }
}

#[test]
fn choice_disabled_empty_string_is_enabled() {
    // R4: disabled is active iff true OR a non-empty string. "" -> enabled.
    let mut c = Choice::new("a", "a");
    c.disabled = Some(Value::String(String::new()));
    assert!(!c.is_disabled(), "empty-string disabled means enabled");

    let mut c2 = Choice::new("b", "b");
    c2.disabled = Some(Value::Bool(false));
    assert!(!c2.is_disabled());
}

#[test]
fn choice_disabled_states() {
    let c1 = Choice::new("a", "a");
    assert!(!c1.is_disabled());

    let mut c2 = Choice::new("b", "b");
    c2.disabled = Some(Value::Bool(true));
    assert!(c2.is_disabled());

    let mut c3 = Choice::new("c", "c");
    c3.disabled = Some(Value::String("coming soon".into()));
    assert!(c3.is_disabled());
    assert_eq!(c3.disabled_reason(), Some("coming soon"));
}

#[test]
fn separator_default() {
    let s = Separator::default();
    assert_eq!(s.kind, "separator");
    assert_eq!(s.text, "────────");
}

#[test]
fn choice_to_json() {
    let c = Choice::new("Go", "go");
    let item = ChoiceItem::Choice(c);
    let json = item.to_json();
    assert_eq!(json["name"], "Go");
    assert_eq!(json["value"], "go");
}

#[test]
fn separator_to_json() {
    let s = Separator::new("===");
    let item = ChoiceItem::Separator(s);
    let json = item.to_json();
    assert_eq!(json["type"], "separator");
    assert_eq!(json["text"], "===");
}
