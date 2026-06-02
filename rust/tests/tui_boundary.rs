//! TUI boundary tests for inquirer-ai.
//!
//! Tests choice construction edge cases, filtering behaviour,
//! large choice lists, unicode, duplicates, and value types.
//!
//! Strategy:
//! - Error paths (empty/all-disabled/separators-only) can be tested directly
//!   because select()/checkbox() return Err before entering the terminal loop.
//! - Valid-choice paths are tested via subprocess in agent mode (with
//!   INQUIRER_AI_TRANSPORT=stdio to force stdio instead of socket), piping
//!   JSON answers to stdin. Results are communicated via exit codes because
//!   the test harness captures stderr.
//! - Data-structure tests (Choice, Separator, parse, to_json) run in-process.

use inquirer_ai::choice::{parse_choice, parse_choice_from_value, Choice, ChoiceItem, Separator};
use inquirer_ai::errors::InquirerError;
use inquirer_ai::prompts::expand::{validate_expand, ExpandChoice};
use proptest::prelude::*;
use serde_json::{json, Value};
use std::io::Write;

// =========================================================================
// Helper: run a Rust snippet in a subprocess with INQUIRER_AI_MODE=agent
// =========================================================================

/// Build and run the test binary's ignored helper in agent mode.
/// Writes `answer_json` lines to stdin (one per prompt round).
/// Returns (exit_code, stdout, stderr).
fn run_agent_subprocess(helper_name: &str, answers: &[Value]) -> (Option<i32>, String, String) {
    let exe = std::env::current_exe().unwrap();
    let mut cmd = std::process::Command::new(exe);
    cmd.arg("--ignored")
        .arg(helper_name)
        .env("INQUIRER_AI_MODE", "agent")
        .env("INQUIRER_AI_TRANSPORT", "stdio")
        .env(format!("RUN_{}", helper_name.to_uppercase()), "1")
        .env_remove("INQUIRER_AI_FD_OUT")
        .env_remove("INQUIRER_AI_FD_IN")
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());

    let mut child = cmd.spawn().expect("Failed to spawn subprocess");

    // Write all answer lines to stdin, then close it
    {
        let stdin = child.stdin.as_mut().unwrap();
        for ans in answers {
            let line = json!({"answer": ans}).to_string();
            writeln!(stdin, "{line}").unwrap();
        }
    }

    let output = child.wait_with_output().expect("Failed to wait");
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    (output.status.code(), stdout, stderr)
}

// Exit code conventions for subprocess helpers:
// 0 = success (prompt returned expected value)
// 1 = prompt returned wrong value
// 2 = prompt returned unexpected error

// =========================================================================
// 1. Choice with disabled flag filtered out
// =========================================================================

#[test]
fn select_all_disabled_returns_invalid_choice() {
    let mut c1 = Choice::new("A", json!("a"));
    c1.disabled = Some(json!(true));
    let mut c2 = Choice::new("B", json!("b"));
    c2.disabled = Some(json!("reason"));

    let config = inquirer_ai::SelectConfig::new(
        "Pick",
        vec![ChoiceItem::Choice(c1), ChoiceItem::Choice(c2)],
    );
    let result = inquirer_ai::select(config);
    assert!(
        matches!(result, Err(InquirerError::InvalidChoice(_))),
        "All-disabled should yield InvalidChoice, got: {result:?}"
    );
}

#[test]
fn checkbox_all_disabled_returns_invalid_choice() {
    let mut c1 = Choice::new("X", json!("x"));
    c1.disabled = Some(json!(true));
    let config = inquirer_ai::CheckboxConfig::new("Check", vec![ChoiceItem::Choice(c1)]);
    let result = inquirer_ai::checkbox(config);
    assert!(
        matches!(result, Err(InquirerError::InvalidChoice(_))),
        "All-disabled checkbox should yield InvalidChoice, got: {result:?}"
    );
}

#[test]
fn disabled_with_string_reason_is_disabled() {
    let mut c = Choice::new("item", json!("val"));
    c.disabled = Some(json!("Not available yet"));
    assert!(c.is_disabled());
    assert_eq!(c.disabled_reason(), Some("Not available yet"));
}

#[test]
fn disabled_with_false_is_not_disabled() {
    let mut c = Choice::new("item", json!("val"));
    c.disabled = Some(json!(false));
    assert!(!c.is_disabled());
}

#[test]
fn disabled_with_empty_string_is_not_disabled() {
    let mut c = Choice::new("item", json!("val"));
    c.disabled = Some(json!(""));
    assert!(!c.is_disabled());
}

#[test]
fn disabled_with_number_is_disabled() {
    let mut c = Choice::new("item", json!("val"));
    c.disabled = Some(json!(42));
    assert!(c.is_disabled());
}

#[test]
fn disabled_with_null_is_disabled() {
    let mut c = Choice::new("item", json!("val"));
    c.disabled = Some(json!(null));
    assert!(c.is_disabled());
}

/// Agent-mode test: disabled choices cannot be selected.
/// First answer is a disabled value (rejected), second is a valid value.
#[test]
fn agent_disabled_choice_filtered_out() {
    let (code, stdout, stderr) = run_agent_subprocess(
        "agent_disabled_choice_helper",
        &[
            json!("disabled_val"),
            json!("enabled_val"),
            json!("enabled_val"),
        ],
    );
    // stdout should contain a validation_error for the disabled choice
    assert!(
        stdout.contains("validation_error"),
        "Should have sent validation_error for disabled choice. stdout: {stdout}, stderr: {stderr}"
    );
    assert_eq!(
        code,
        Some(0),
        "Should succeed after retrying with valid choice. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_disabled_choice_helper() {
    if std::env::var("RUN_AGENT_DISABLED_CHOICE_HELPER").is_err() {
        return;
    }
    let mut disabled = Choice::new("Disabled", json!("disabled_val"));
    disabled.disabled = Some(json!(true));
    let enabled = Choice::new("Enabled", json!("enabled_val"));
    let choices = vec![ChoiceItem::Choice(disabled), ChoiceItem::Choice(enabled)];
    let config = inquirer_ai::SelectConfig::new("Pick", choices);
    match inquirer_ai::select(config) {
        Ok(v) if v == json!("enabled_val") => std::process::exit(0),
        Ok(_) => std::process::exit(1),
        Err(_) => std::process::exit(2),
    }
}

// =========================================================================
// 2. Separator not treated as selectable choice
// =========================================================================

#[test]
fn separators_only_yields_invalid_choice_for_select() {
    let choices = vec![
        ChoiceItem::Separator(Separator::default()),
        ChoiceItem::Separator(Separator::new("--- section ---")),
    ];
    let config = inquirer_ai::SelectConfig::new("Pick", choices);
    let result = inquirer_ai::select(config);
    assert!(
        matches!(result, Err(InquirerError::InvalidChoice(_))),
        "Separators-only should yield InvalidChoice, got: {result:?}"
    );
}

#[test]
fn separators_only_yields_invalid_choice_for_checkbox() {
    let choices = vec![
        ChoiceItem::Separator(Separator::default()),
        ChoiceItem::Separator(Separator::new("section 2")),
    ];
    let config = inquirer_ai::CheckboxConfig::new("Check", choices);
    let result = inquirer_ai::checkbox(config);
    assert!(
        matches!(result, Err(InquirerError::InvalidChoice(_))),
        "Separators-only checkbox should yield InvalidChoice, got: {result:?}"
    );
}

#[test]
fn separator_mixed_with_disabled_is_not_selectable() {
    let sep = ChoiceItem::Separator(Separator::new("---"));
    let mut disabled = Choice::new("Off", json!("off"));
    disabled.disabled = Some(json!(true));

    let choices = vec![sep, ChoiceItem::Choice(disabled)];
    let config = inquirer_ai::SelectConfig::new("Pick", choices);
    let result = inquirer_ai::select(config);
    assert!(
        matches!(result, Err(InquirerError::InvalidChoice(_))),
        "Separator + disabled should yield InvalidChoice, got: {result:?}"
    );
}

#[test]
fn separator_to_json_has_type_field() {
    let s = Separator::new("my section");
    let item = ChoiceItem::Separator(s);
    let j = item.to_json();
    assert_eq!(j["type"], "separator");
    assert_eq!(j["text"], "my section");
}

#[test]
fn parse_separator_from_value() {
    let val = json!({"type": "separator", "text": "section"});
    let item = parse_choice_from_value(val);
    match item {
        ChoiceItem::Separator(s) => assert_eq!(s.text, "section"),
        other => panic!("Expected Separator, got: {other:?}"),
    }
}

/// Agent-mode: separator value cannot be selected; valid choice works.
#[test]
fn agent_separator_not_selectable() {
    let (code, stdout, stderr) = run_agent_subprocess(
        "agent_separator_helper",
        &[json!("---sep---"), json!("valid"), json!("valid")],
    );
    // The separator text should be rejected
    assert!(
        stdout.contains("validation_error") || stdout.contains("Invalid choice"),
        "Should reject separator text. stdout: {stdout}, stderr: {stderr}"
    );
    assert_eq!(
        code,
        Some(0),
        "Should succeed with valid choice. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_separator_helper() {
    if std::env::var("RUN_AGENT_SEPARATOR_HELPER").is_err() {
        return;
    }
    let choices = vec![
        ChoiceItem::Separator(Separator::new("---sep---")),
        ChoiceItem::Choice(Choice::new("Valid", json!("valid"))),
    ];
    let config = inquirer_ai::SelectConfig::new("Pick", choices);
    match inquirer_ai::select(config) {
        Ok(v) if v == json!("valid") => std::process::exit(0),
        Ok(_) => std::process::exit(1),
        Err(_) => std::process::exit(2),
    }
}

// =========================================================================
// 3. Large number of choices (100+)
// =========================================================================

#[test]
fn large_choice_list_construction_200() {
    let choices: Vec<ChoiceItem> = (0..200)
        .map(|i| ChoiceItem::Choice(Choice::new(format!("Option {i}"), json!(i))))
        .collect();
    assert_eq!(choices.len(), 200);
    match &choices[0] {
        ChoiceItem::Choice(c) => assert_eq!(c.name, "Option 0"),
        _ => panic!("Expected Choice"),
    }
    match &choices[199] {
        ChoiceItem::Choice(c) => assert_eq!(c.name, "Option 199"),
        _ => panic!("Expected Choice"),
    }
}

#[test]
fn large_choice_list_construction_500() {
    let choices: Vec<ChoiceItem> = (0..500)
        .map(|i| ChoiceItem::Choice(Choice::new(format!("Item {i}"), json!(i))))
        .collect();
    assert_eq!(choices.len(), 500);
    for (idx, item) in choices.iter().enumerate() {
        let j = item.to_json();
        assert_eq!(j["name"], format!("Item {idx}"));
        assert_eq!(j["value"], json!(idx));
    }
}

#[test]
fn large_choice_list_with_separators_interspersed() {
    let mut choices: Vec<ChoiceItem> = Vec::new();
    for i in 0..150 {
        if i % 25 == 0 {
            choices.push(ChoiceItem::Separator(Separator::new(format!(
                "Section {}",
                i / 25
            ))));
        }
        choices.push(ChoiceItem::Choice(Choice::new(
            format!("Choice {i}"),
            json!(i),
        )));
    }
    // 150 choices + 6 separators (at i=0,25,50,75,100,125)
    assert_eq!(choices.len(), 156);
    match &choices[0] {
        ChoiceItem::Separator(s) => assert_eq!(s.text, "Section 0"),
        _ => panic!("Expected Separator at index 0"),
    }
}

#[test]
fn large_expand_choice_list() {
    let choices: Vec<ExpandChoice> = (b'a'..=b'z')
        .map(|k| {
            let key = String::from(k as char);
            ExpandChoice {
                key: key.clone(),
                name: format!("Option {}", key.to_uppercase()),
                value: json!(key),
            }
        })
        .collect();
    assert_eq!(choices.len(), 26);
    for c in &choices {
        let result = validate_expand(&json!(c.key), &choices);
        assert!(
            result.is_ok(),
            "Key {} should validate, got: {:?}",
            c.key,
            result
        );
    }
}

/// Agent-mode: select from 200 choices.
#[test]
fn agent_large_choice_list_select() {
    let (code, stdout, stderr) =
        run_agent_subprocess("agent_large_select_helper", &[json!("Option 99")]);
    assert_eq!(
        code,
        Some(0),
        "Should select from 200 choices. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_large_select_helper() {
    if std::env::var("RUN_AGENT_LARGE_SELECT_HELPER").is_err() {
        return;
    }
    let choices: Vec<ChoiceItem> = (0..200)
        .map(|i| ChoiceItem::Choice(Choice::new(format!("Option {i}"), json!(i))))
        .collect();
    let config = inquirer_ai::SelectConfig::new("Pick one of 200", choices);
    match inquirer_ai::select(config) {
        Ok(v) if v == json!(99) => std::process::exit(0),
        Ok(v) => {
            // Write to fd 2 directly to bypass test harness capture
            let _ = std::io::stderr().write_all(format!("Wrong value: {v}\n").as_bytes());
            std::process::exit(1);
        }
        Err(e) => {
            let _ = std::io::stderr().write_all(format!("Error: {e}\n").as_bytes());
            std::process::exit(2);
        }
    }
}

// =========================================================================
// 4. Unicode choice names
// =========================================================================

#[test]
fn unicode_choice_name_cjk() {
    let c = Choice::new("选项一", json!("opt1"));
    assert_eq!(c.name, "选项一");
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["name"], "选项一");
}

#[test]
fn unicode_choice_name_emoji() {
    let c = Choice::new("\u{1F680} Launch", json!("launch"));
    assert_eq!(c.name, "\u{1F680} Launch");
}

#[test]
fn unicode_choice_name_arabic() {
    let c = Choice::new("خيار", json!("option"));
    assert_eq!(c.name, "خيار");
}

#[test]
fn unicode_choice_name_mixed_scripts() {
    let c = Choice::new("日本語 English العربية", json!("mixed"));
    assert_eq!(c.name, "日本語 English العربية");
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["name"], "日本語 English العربية");
}

#[test]
fn unicode_separator_text() {
    let s = Separator::new("═══ 分组 ═══");
    assert_eq!(s.text, "═══ 分组 ═══");
}

#[test]
fn parse_choice_from_unicode_string() {
    let item = parse_choice("日本語テスト");
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "日本語テスト");
            assert_eq!(c.value, json!("日本語テスト"));
        }
        _ => panic!("Expected Choice"),
    }
}

/// Agent-mode: unicode choice names work end-to-end.
#[test]
fn agent_unicode_choices_select() {
    let (code, stdout, stderr) = run_agent_subprocess("agent_unicode_helper", &[json!("选项一")]);
    assert_eq!(
        code,
        Some(0),
        "Should select unicode choice. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_unicode_helper() {
    if std::env::var("RUN_AGENT_UNICODE_HELPER").is_err() {
        return;
    }
    let choices = vec![
        ChoiceItem::Choice(Choice::new("选项一", json!("opt1"))),
        ChoiceItem::Choice(Choice::new("Привет", json!("opt2"))),
        ChoiceItem::Choice(Choice::new("مرحبا", json!("opt3"))),
    ];
    let config = inquirer_ai::SelectConfig::new("Pick", choices);
    match inquirer_ai::select(config) {
        Ok(v) if v == json!("opt1") => std::process::exit(0),
        Ok(_) => std::process::exit(1),
        Err(_) => std::process::exit(2),
    }
}

// =========================================================================
// 5. Choice with empty name
// =========================================================================

#[test]
fn empty_name_choice_is_valid() {
    let c = Choice::new("", json!("empty"));
    assert_eq!(c.name, "");
    assert!(!c.is_disabled());
}

#[test]
fn empty_name_choice_to_json() {
    let item = ChoiceItem::Choice(Choice::new("", json!("val")));
    let j = item.to_json();
    assert_eq!(j["name"], "");
    assert_eq!(j["value"], "val");
}

#[test]
fn parse_choice_from_empty_string() {
    let item = parse_choice("");
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.name, "");
            assert_eq!(c.value, json!(""));
        }
        _ => panic!("Expected Choice"),
    }
}

#[test]
fn empty_separator_text() {
    let s = Separator::new("");
    assert_eq!(s.text, "");
}

/// Agent-mode: empty-name choice can be selected by value.
#[test]
fn agent_empty_name_select() {
    let (code, stdout, stderr) =
        run_agent_subprocess("agent_empty_name_helper", &[json!("empty_val")]);
    assert_eq!(
        code,
        Some(0),
        "Should select empty-name choice by value. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_empty_name_helper() {
    if std::env::var("RUN_AGENT_EMPTY_NAME_HELPER").is_err() {
        return;
    }
    let choices = vec![
        ChoiceItem::Choice(Choice::new("", json!("empty_val"))),
        ChoiceItem::Choice(Choice::new("Normal", json!("normal"))),
    ];
    let config = inquirer_ai::SelectConfig::new("Pick", choices);
    match inquirer_ai::select(config) {
        Ok(v) if v == json!("empty_val") => std::process::exit(0),
        Ok(_) => std::process::exit(1),
        Err(_) => std::process::exit(2),
    }
}

// =========================================================================
// 6. Duplicate choice values
// =========================================================================

#[test]
fn duplicate_values_construction_accepted() {
    let choices = vec![
        ChoiceItem::Choice(Choice::new("Option A", json!("same"))),
        ChoiceItem::Choice(Choice::new("Option B", json!("same"))),
        ChoiceItem::Choice(Choice::new("Option C", json!("same"))),
    ];
    assert_eq!(choices.len(), 3);
    for item in &choices {
        let j = item.to_json();
        assert_eq!(j["value"], "same");
    }
}

#[test]
fn duplicate_names_different_values_construction() {
    let choices = [
        ChoiceItem::Choice(Choice::new("Same Name", json!("val1"))),
        ChoiceItem::Choice(Choice::new("Same Name", json!("val2"))),
    ];
    let j0 = choices[0].to_json();
    let j1 = choices[1].to_json();
    assert_eq!(j0["name"], "Same Name");
    assert_eq!(j1["name"], "Same Name");
    assert_ne!(j0["value"], j1["value"]);
}

#[test]
fn duplicate_expand_keys_rejected() {
    let choices = vec![
        ExpandChoice {
            key: "a".into(),
            name: "First".into(),
            value: json!("first"),
        },
        ExpandChoice {
            key: "a".into(),
            name: "Second".into(),
            value: json!("second"),
        },
    ];
    let config = inquirer_ai::ExpandConfig::new("Pick", choices);
    let result = inquirer_ai::expand(config);
    assert!(
        matches!(result, Err(InquirerError::InvalidChoice(ref msg)) if msg.contains("Duplicate")),
        "Duplicate expand keys should error, got: {result:?}"
    );
}

/// Agent-mode: duplicate values -- selecting by value returns it.
#[test]
fn agent_duplicate_values_select() {
    let (code, stdout, stderr) =
        run_agent_subprocess("agent_duplicate_values_helper", &[json!("same")]);
    assert_eq!(
        code,
        Some(0),
        "Duplicate values should still allow selection. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_duplicate_values_helper() {
    if std::env::var("RUN_AGENT_DUPLICATE_VALUES_HELPER").is_err() {
        return;
    }
    let choices = vec![
        ChoiceItem::Choice(Choice::new("Option A", json!("same"))),
        ChoiceItem::Choice(Choice::new("Option B", json!("same"))),
    ];
    let config = inquirer_ai::SelectConfig::new("Pick", choices);
    match inquirer_ai::select(config) {
        Ok(v) if v == json!("same") => std::process::exit(0),
        Ok(_) => std::process::exit(1),
        Err(_) => std::process::exit(2),
    }
}

// =========================================================================
// 7. Choice value types (string, number, bool, null)
// =========================================================================

#[test]
fn choice_value_string() {
    let c = Choice::new("String val", json!("hello"));
    assert_eq!(c.value, json!("hello"));
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["value"], "hello");
}

#[test]
fn choice_value_integer() {
    let c = Choice::new("Int val", json!(42));
    assert_eq!(c.value, json!(42));
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["value"], 42);
}

#[test]
fn choice_value_float() {
    let c = Choice::new("Float val", json!(3.25));
    assert_eq!(c.value, json!(3.25));
}

#[test]
fn choice_value_bool_true() {
    let c = Choice::new("Bool val", json!(true));
    assert_eq!(c.value, json!(true));
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["value"], true);
}

#[test]
fn choice_value_bool_false() {
    let c = Choice::new("Bool false", json!(false));
    assert_eq!(c.value, json!(false));
}

#[test]
fn choice_value_null() {
    let c = Choice::new("Null val", json!(null));
    assert_eq!(c.value, json!(null));
    let j = ChoiceItem::Choice(c).to_json();
    assert!(j["value"].is_null());
}

#[test]
fn choice_value_nested_object() {
    let val = json!({"key": "value", "nested": [1, 2, 3]});
    let c = Choice::new("Object val", val.clone());
    assert_eq!(c.value, val);
}

#[test]
fn choice_value_array() {
    let val = json!([1, "two", true, null]);
    let c = Choice::new("Array val", val.clone());
    assert_eq!(c.value, val);
}

#[test]
fn parse_choice_from_value_number() {
    let item = parse_choice_from_value(json!(42));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.value, json!(42));
            assert_eq!(c.name, "42");
        }
        _ => panic!("Expected Choice"),
    }
}

#[test]
fn parse_choice_from_value_bool() {
    let item = parse_choice_from_value(json!(true));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.value, json!(true));
            assert_eq!(c.name, "true");
        }
        _ => panic!("Expected Choice"),
    }
}

#[test]
fn parse_choice_from_value_null() {
    let item = parse_choice_from_value(json!(null));
    match item {
        ChoiceItem::Choice(c) => {
            assert_eq!(c.value, json!(null));
            assert_eq!(c.name, "null");
        }
        _ => panic!("Expected Choice"),
    }
}

/// Agent-mode: numeric value type works in select.
#[test]
fn agent_mixed_value_types() {
    let (code, stdout, stderr) = run_agent_subprocess("agent_mixed_types_helper", &[json!(42)]);
    assert_eq!(
        code,
        Some(0),
        "Should select numeric value. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_mixed_types_helper() {
    if std::env::var("RUN_AGENT_MIXED_TYPES_HELPER").is_err() {
        return;
    }
    let choices = vec![
        ChoiceItem::Choice(Choice::new("String", json!("str"))),
        ChoiceItem::Choice(Choice::new("Number", json!(42))),
        ChoiceItem::Choice(Choice::new("Bool", json!(true))),
        ChoiceItem::Choice(Choice::new("Null", json!(null))),
    ];
    let config = inquirer_ai::SelectConfig::new("Pick a type", choices);
    match inquirer_ai::select(config) {
        Ok(v) if v == json!(42) => std::process::exit(0),
        Ok(_) => std::process::exit(1),
        Err(_) => std::process::exit(2),
    }
}

/// Agent-mode: checkbox with mixed value types.
#[test]
fn agent_checkbox_mixed_types() {
    let (code, stdout, stderr) =
        run_agent_subprocess("agent_checkbox_mixed_helper", &[json!(["str", 42])]);
    assert_eq!(
        code,
        Some(0),
        "Should select mixed types in checkbox. stdout: {stdout}, stderr: {stderr}"
    );
}

#[test]
#[ignore]
fn agent_checkbox_mixed_helper() {
    if std::env::var("RUN_AGENT_CHECKBOX_MIXED_HELPER").is_err() {
        return;
    }
    let choices = vec![
        ChoiceItem::Choice(Choice::new("String", json!("str"))),
        ChoiceItem::Choice(Choice::new("Number", json!(42))),
        ChoiceItem::Choice(Choice::new("Bool", json!(true))),
    ];
    let config = inquirer_ai::CheckboxConfig::new("Check", choices);
    match inquirer_ai::checkbox(config) {
        Ok(v) if v == vec![json!("str"), json!(42)] => std::process::exit(0),
        Ok(_) => std::process::exit(1),
        Err(_) => std::process::exit(2),
    }
}

#[test]
fn expand_validate_by_key() {
    let choices = vec![
        ExpandChoice {
            key: "y".into(),
            name: "Yes".into(),
            value: json!(true),
        },
        ExpandChoice {
            key: "n".into(),
            name: "No".into(),
            value: json!(false),
        },
    ];
    assert_eq!(validate_expand(&json!("y"), &choices).unwrap(), json!(true));
    assert_eq!(
        validate_expand(&json!("n"), &choices).unwrap(),
        json!(false)
    );
    assert!(validate_expand(&json!("x"), &choices).is_err());
}

#[test]
fn expand_validate_by_name() {
    let choices = vec![ExpandChoice {
        key: "y".into(),
        name: "Yes".into(),
        value: json!("yes_val"),
    }];
    assert_eq!(
        validate_expand(&json!("Yes"), &choices).unwrap(),
        json!("yes_val")
    );
}

#[test]
fn expand_validate_by_value() {
    let choices = vec![ExpandChoice {
        key: "d".into(),
        name: "Delete".into(),
        value: json!("delete"),
    }];
    assert_eq!(
        validate_expand(&json!("delete"), &choices).unwrap(),
        json!("delete")
    );
}

#[test]
fn expand_validate_case_insensitive_key() {
    let choices = vec![ExpandChoice {
        key: "y".into(),
        name: "Yes".into(),
        value: json!(true),
    }];
    assert_eq!(validate_expand(&json!("Y"), &choices).unwrap(), json!(true));
}

#[test]
fn expand_empty_choices_rejected() {
    let config = inquirer_ai::ExpandConfig::new("Pick", vec![]);
    let result = inquirer_ai::expand(config);
    assert!(
        matches!(result, Err(InquirerError::InvalidChoice(_))),
        "Empty expand choices should be rejected, got: {result:?}"
    );
}

#[test]
fn expand_validate_non_string_input() {
    let choices = vec![ExpandChoice {
        key: "y".into(),
        name: "Yes".into(),
        value: json!(true),
    }];
    assert!(validate_expand(&json!(42), &choices).is_err());
    assert!(validate_expand(&json!(true), &choices).is_err());
    assert!(validate_expand(&json!(null), &choices).is_err());
}

// =========================================================================
// 8. Property-based: random choice names never cause panics
// =========================================================================

proptest! {
    /// Constructing a Choice with any arbitrary string name should never panic.
    #[test]
    fn choice_new_arbitrary_name_no_panic(name in "\\PC{0,200}") {
        let c = Choice::new(name.clone(), json!("val"));
        prop_assert_eq!(&c.name, &name);
    }

    /// parse_choice with arbitrary UTF-8 input should never panic.
    #[test]
    fn parse_choice_arbitrary_no_panic(s in "\\PC{0,200}") {
        let item = parse_choice(&s);
        match item {
            ChoiceItem::Choice(c) => {
                prop_assert_eq!(&c.name, &s);
            }
            _ => prop_assert!(false, "parse_choice should always return Choice"),
        }
    }

    /// parse_choice_from_value with arbitrary string values never panics.
    #[test]
    fn parse_choice_from_value_arbitrary_string_no_panic(s in "\\PC{0,200}") {
        let val = Value::String(s.clone());
        let item = parse_choice_from_value(val);
        match item {
            ChoiceItem::Choice(c) => {
                prop_assert_eq!(&c.name, &s);
            }
            _ => prop_assert!(false, "expected Choice for string input"),
        }
    }

    /// to_json roundtrip: creating a Choice and serializing should never panic.
    #[test]
    fn choice_to_json_roundtrip_no_panic(
        name in "\\PC{0,100}",
        value_str in "\\PC{0,100}",
    ) {
        let c = Choice::new(name.clone(), json!(value_str));
        let item = ChoiceItem::Choice(c);
        let j = item.to_json();
        prop_assert_eq!(j["name"].clone(), json!(name));
    }

    /// Separator with arbitrary text never panics.
    #[test]
    fn separator_arbitrary_text_no_panic(text in "\\PC{0,200}") {
        let s = Separator::new(text.clone());
        prop_assert_eq!(&s.text, &text);
        let item = ChoiceItem::Separator(s);
        let j = item.to_json();
        prop_assert_eq!(j["text"].clone(), json!(text));
    }

    /// validate_expand with random key input should never panic.
    #[test]
    fn expand_validate_random_input_no_panic(input in "\\PC{0,50}") {
        let choices = vec![
            ExpandChoice { key: "a".into(), name: "Alpha".into(), value: json!("a") },
            ExpandChoice { key: "b".into(), name: "Beta".into(), value: json!("b") },
        ];
        let _result = validate_expand(&json!(input), &choices);
    }

    /// Choice with arbitrary disabled values should not panic on is_disabled().
    #[test]
    fn is_disabled_arbitrary_value_no_panic(val in prop_oneof![
        Just(json!(null)),
        any::<bool>().prop_map(|b| json!(b)),
        any::<i64>().prop_map(|n| json!(n)),
        "\\PC{0,50}".prop_map(|s| json!(s)),
        Just(json!([])),
        Just(json!({})),
    ]) {
        let mut c = Choice::new("test", json!("val"));
        c.disabled = Some(val);
        let _ = c.is_disabled(); // should never panic
        let _ = c.disabled_reason(); // should never panic
    }

    /// Large random choice list: construction + serialization never panics.
    #[test]
    fn large_random_choice_list_no_panic(
        names in proptest::collection::vec("\\PC{0,50}", 100..150),
    ) {
        let choices: Vec<ChoiceItem> = names
            .iter()
            .enumerate()
            .map(|(i, n)| ChoiceItem::Choice(Choice::new(n.as_str(), json!(i))))
            .collect();
        for item in &choices {
            let _j = item.to_json();
        }
        prop_assert!(choices.len() >= 100);
    }

    /// Random choice names with mixed scripts should round-trip through to_json.
    #[test]
    fn unicode_choice_roundtrip_no_panic(
        name in "[\\p{Han}\\p{Cyrillic}\\p{Arabic}a-z0-9 ]{1,50}",
    ) {
        let c = Choice::new(name.clone(), json!(name.clone()));
        let item = ChoiceItem::Choice(c);
        let j = item.to_json();
        prop_assert_eq!(j["name"].as_str().unwrap(), name.as_str());
    }
}
