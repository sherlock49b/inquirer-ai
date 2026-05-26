//! TUI rendering tests for inquirer-ai.
//!
//! Tests the terminal formatting helpers, theme colour output, and
//! rendering-related pure logic that can be exercised without a real
//! terminal or raw-mode.  Property-based tests ensure that arbitrary
//! inputs never cause panics in rendering paths.

use inquirer_ai::choice::{Choice, ChoiceItem, Separator};
use inquirer_ai::prompts::confirm::coerce_bool;
use inquirer_ai::prompts::expand::{validate_expand, ExpandChoice};
use inquirer_ai::prompts::number::{validate_number, NumberConfig};
use inquirer_ai::prompts::rawlist::validate_rawlist;
use inquirer_ai::terminal::{format_error, format_question, format_success};
use inquirer_ai::theme::{ansi_color, BOLD, DEFAULT_THEME, RESET};
use proptest::prelude::*;
use regex::Regex;
use serde_json::json;

// =========================================================================
// Helper: strip ANSI escape sequences
// =========================================================================

fn strip_ansi(s: &str) -> String {
    let re = Regex::new(r"\x1b\[[0-9;]*[a-zA-Z]").unwrap();
    re.replace_all(s, "").to_string()
}

// =========================================================================
// 1. format_question tests
// =========================================================================

#[test]
fn format_question_contains_message_and_suffix() {
    let q = format_question("Your name", " (default)");
    let plain = strip_ansi(&q);
    assert!(
        plain.contains("Your name"),
        "format_question should contain the message, got: {plain}"
    );
    assert!(
        plain.contains("(default)"),
        "format_question should contain the suffix, got: {plain}"
    );
    assert!(
        plain.contains('?'),
        "format_question should contain the question symbol, got: {plain}"
    );
    // Must end with RESET + space for user input (colon is before RESET)
    let expected_ending = format!(":{RESET} ");
    assert!(
        q.ends_with(&expected_ending),
        "format_question should end with colon+RESET+space, got: {q:?}"
    );
}

#[test]
fn format_question_empty_suffix() {
    let q = format_question("Do thing", "");
    let plain = strip_ansi(&q);
    assert!(plain.contains("Do thing"));
    assert!(plain.contains(':'));
}

#[test]
fn format_question_contains_ansi_codes() {
    let q = format_question("msg", "");
    // Should contain at least one ANSI escape (colour of the question mark)
    assert!(
        q.contains("\x1b["),
        "format_question should produce ANSI-styled output"
    );
    // Should contain RESET
    assert!(
        q.contains(RESET),
        "format_question should contain RESET sequence"
    );
    // Should contain BOLD
    assert!(
        q.contains(BOLD),
        "format_question should contain BOLD sequence"
    );
}

#[test]
fn format_question_uses_theme_question_colour() {
    let expected_colour = ansi_color(DEFAULT_THEME.question);
    let q = format_question("test", "");
    assert!(
        q.contains(&expected_colour),
        "format_question should use the theme question colour"
    );
}

// =========================================================================
// 2. format_success tests
// =========================================================================

#[test]
fn format_success_contains_message_and_answer() {
    let s = format_success("Your name", "Alice");
    let plain = strip_ansi(&s);
    assert!(
        plain.contains("Your name"),
        "format_success should contain the message, got: {plain}"
    );
    assert!(
        plain.contains("Alice"),
        "format_success should contain the answer, got: {plain}"
    );
    assert!(
        plain.contains(DEFAULT_THEME.sym_success),
        "format_success should contain the success symbol, got: {plain}"
    );
}

#[test]
fn format_success_uses_theme_colours() {
    let s = format_success("msg", "ans");
    let success_colour = ansi_color(DEFAULT_THEME.success);
    let answer_colour = ansi_color(DEFAULT_THEME.answer);
    assert!(
        s.contains(&success_colour),
        "format_success should use success colour"
    );
    assert!(
        s.contains(&answer_colour),
        "format_success should use answer colour"
    );
}

#[test]
fn format_success_empty_answer() {
    let s = format_success("Choose", "");
    let plain = strip_ansi(&s);
    assert!(plain.contains("Choose"));
}

// =========================================================================
// 3. format_error tests
// =========================================================================

#[test]
fn format_error_contains_message() {
    let e = format_error("Something went wrong");
    let plain = strip_ansi(&e);
    assert!(
        plain.contains("Something went wrong"),
        "format_error should contain the error message, got: {plain}"
    );
}

#[test]
fn format_error_uses_error_colour() {
    let e = format_error("err");
    let error_colour = ansi_color(DEFAULT_THEME.error);
    assert!(
        e.contains(&error_colour),
        "format_error should use the error colour"
    );
}

#[test]
fn format_error_contains_reset() {
    let e = format_error("err");
    assert!(
        e.contains(RESET),
        "format_error should contain RESET to stop colour bleeding"
    );
}

// =========================================================================
// 4. Theme / ansi_color tests (complement existing theme.rs tests)
// =========================================================================

#[test]
fn ansi_color_all_theme_colours_are_valid() {
    // Every colour in DEFAULT_THEME should produce a valid ANSI 24-bit colour
    let colours = [
        DEFAULT_THEME.question,
        DEFAULT_THEME.success,
        DEFAULT_THEME.highlight,
        DEFAULT_THEME.selected,
        DEFAULT_THEME.answer,
        DEFAULT_THEME.error,
        DEFAULT_THEME.muted,
    ];
    let re = Regex::new(r"^\x1b\[38;2;\d{1,3};\d{1,3};\d{1,3}m$").unwrap();
    for hex in &colours {
        let ansi = ansi_color(hex);
        assert!(
            re.is_match(&ansi),
            "ansi_color({hex:?}) should produce a valid 24-bit ANSI colour, got: {ansi:?}"
        );
    }
}

#[test]
fn ansi_color_known_values() {
    assert_eq!(ansi_color("#000000"), "\x1b[38;2;0;0;0m");
    assert_eq!(ansi_color("#ffffff"), "\x1b[38;2;255;255;255m");
    assert_eq!(ansi_color("#808080"), "\x1b[38;2;128;128;128m");
}

#[test]
fn ansi_color_case_insensitive_hex() {
    assert_eq!(ansi_color("#AABBCC"), ansi_color("#aabbcc"));
}

// =========================================================================
// 5. strip_ansi helper correctness
// =========================================================================

#[test]
fn strip_ansi_removes_colour_codes() {
    let input = "\x1b[38;2;255;0;0mhello\x1b[0m";
    assert_eq!(strip_ansi(input), "hello");
}

#[test]
fn strip_ansi_preserves_plain_text() {
    assert_eq!(strip_ansi("no codes here"), "no codes here");
}

#[test]
fn strip_ansi_handles_bold_and_reset() {
    let input = format!("{BOLD}bold text{RESET}");
    assert_eq!(strip_ansi(&input), "bold text");
}

#[test]
fn strip_ansi_handles_multiple_codes() {
    let input = "\x1b[1m\x1b[38;2;1;2;3mtext\x1b[0m rest\x1b[38;2;4;5;6m more\x1b[0m";
    assert_eq!(strip_ansi(input), "text rest more");
}

// =========================================================================
// 6. Format output structure tests
// =========================================================================

#[test]
fn format_question_structure_matches_pattern() {
    // Expected: "{colour}?{RESET} {BOLD}message suffix:{RESET} "
    let q = format_question("Pick one", " (Y/n)");
    let plain = strip_ansi(&q);
    // Pattern: "? Pick one (Y/n): "
    assert_eq!(plain, "? Pick one (Y/n): ");
}

#[test]
fn format_success_structure_matches_pattern() {
    let s = format_success("Pick one", "Option A");
    let plain = strip_ansi(&s);
    // Pattern: "checkmark message answer"
    let expected = format!("{} Pick one Option A", DEFAULT_THEME.sym_success);
    assert_eq!(plain, expected);
}

#[test]
fn format_error_structure_matches_pattern() {
    let e = format_error("Invalid input");
    let plain = strip_ansi(&e);
    assert_eq!(plain, "  Invalid input");
}

// =========================================================================
// 7. Validation function rendering paths
// =========================================================================

#[test]
fn validate_number_error_messages_are_human_readable() {
    let config = NumberConfig {
        message: "Age".into(),
        default: None,
        min: Some(0.0),
        max: Some(120.0),
        step: None,
        float_allowed: false,
        keep_input: true,
    };

    // Below min
    let err = validate_number(&json!(-1), &config).unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("at least"),
        "min violation message should be readable: {msg}"
    );

    // Above max
    let err = validate_number(&json!(200), &config).unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("at most"),
        "max violation message should be readable: {msg}"
    );

    // Float when not allowed
    let err = validate_number(&json!("3.5"), &config).unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("ecimal") || msg.contains("not allowed"),
        "float violation message should be readable: {msg}"
    );
}

#[test]
fn validate_number_step_error_message() {
    let config = NumberConfig {
        message: "Value".into(),
        default: None,
        min: Some(0.0),
        max: Some(100.0),
        step: Some(5.0),
        float_allowed: true,
        keep_input: true,
    };
    let err = validate_number(&json!("7"), &config).unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("multiple"),
        "step violation message should mention 'multiple': {msg}"
    );
}

#[test]
fn validate_number_nan_and_infinity() {
    let config = NumberConfig::new("x");
    let err = validate_number(&json!("NaN"), &config);
    assert!(err.is_err(), "NaN should be rejected");
    let err = validate_number(&json!("Infinity"), &config);
    assert!(err.is_err(), "Infinity should be rejected");
}

#[test]
fn validate_number_bool_rejected() {
    let config = NumberConfig::new("x");
    let err = validate_number(&json!(true), &config).unwrap_err();
    assert!(
        err.to_string().contains("boolean"),
        "Bool rejection should mention 'boolean': {}",
        err
    );
}

#[test]
fn validate_rawlist_by_index() {
    let choices = vec![
        Choice::new("Alpha", json!("a")),
        Choice::new("Beta", json!("b")),
        Choice::new("Gamma", json!("c")),
    ];
    assert_eq!(validate_rawlist(&json!(1), &choices).unwrap(), json!("a"));
    assert_eq!(validate_rawlist(&json!(2), &choices).unwrap(), json!("b"));
    assert_eq!(validate_rawlist(&json!(3), &choices).unwrap(), json!("c"));
}

#[test]
fn validate_rawlist_by_name() {
    let choices = vec![
        Choice::new("Alpha", json!("a")),
        Choice::new("Beta", json!("b")),
    ];
    assert_eq!(
        validate_rawlist(&json!("Alpha"), &choices).unwrap(),
        json!("a")
    );
    assert_eq!(
        validate_rawlist(&json!("Beta"), &choices).unwrap(),
        json!("b")
    );
}

#[test]
fn validate_rawlist_by_value() {
    let choices = vec![Choice::new("Item", json!(42))];
    assert_eq!(validate_rawlist(&json!(42), &choices).unwrap(), json!(42));
}

#[test]
fn validate_rawlist_out_of_range() {
    let choices = vec![Choice::new("Only", json!("only"))];
    assert!(validate_rawlist(&json!(0), &choices).is_err());
    assert!(validate_rawlist(&json!(2), &choices).is_err());
    assert!(validate_rawlist(&json!("nonexistent"), &choices).is_err());
}

#[test]
fn coerce_bool_known_values() {
    assert!(coerce_bool(&json!(true)));
    assert!(!coerce_bool(&json!(false)));
    assert!(coerce_bool(&json!("y")));
    assert!(coerce_bool(&json!("yes")));
    assert!(coerce_bool(&json!("YES")));
    assert!(coerce_bool(&json!("true")));
    assert!(coerce_bool(&json!("1")));
    assert!(!coerce_bool(&json!("n")));
    assert!(!coerce_bool(&json!("no")));
    assert!(!coerce_bool(&json!("false")));
    assert!(!coerce_bool(&json!("0")));
    assert!(!coerce_bool(&json!("random")));
    assert!(!coerce_bool(&json!(null)));
    assert!(coerce_bool(&json!(1)));
    assert!(!coerce_bool(&json!(0)));
    assert!(coerce_bool(&json!(-1)));
}

#[test]
fn validate_expand_produces_correct_value() {
    let choices = vec![
        ExpandChoice {
            key: "y".into(),
            name: "Yes".into(),
            value: json!("yes_result"),
        },
        ExpandChoice {
            key: "n".into(),
            name: "No".into(),
            value: json!("no_result"),
        },
        ExpandChoice {
            key: "d".into(),
            name: "Diff".into(),
            value: json!({"action": "diff"}),
        },
    ];
    assert_eq!(
        validate_expand(&json!("y"), &choices).unwrap(),
        json!("yes_result")
    );
    assert_eq!(
        validate_expand(&json!("N"), &choices).unwrap(),
        json!("no_result")
    );
    assert_eq!(
        validate_expand(&json!("Diff"), &choices).unwrap(),
        json!({"action": "diff"})
    );
    assert!(validate_expand(&json!("x"), &choices).is_err());
}

// =========================================================================
// 8. Choice rendering data construction
// =========================================================================

#[test]
fn choice_description_preserved() {
    let mut c = Choice::new("Deploy", json!("deploy"));
    c.description = Some("Deploy to production".into());
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["description"], "Deploy to production");
}

#[test]
fn choice_short_preserved() {
    let mut c = Choice::new("Very Long Option Name", json!("long"));
    c.short = Some("Short".into());
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["short"], "Short");
}

#[test]
fn disabled_choice_with_reason_in_json() {
    let mut c = Choice::new("Premium", json!("premium"));
    c.disabled = Some(json!("Requires subscription"));
    let j = ChoiceItem::Choice(c).to_json();
    assert_eq!(j["disabled"], "Requires subscription");
}

// =========================================================================
// 9. Formatting with special characters
// =========================================================================

#[test]
fn format_question_with_unicode_message() {
    let q = format_question("选择一个选项", "");
    let plain = strip_ansi(&q);
    assert!(plain.contains("选择一个选项"));
}

#[test]
fn format_success_with_unicode() {
    let s = format_success("名前", "太郎");
    let plain = strip_ansi(&s);
    assert!(plain.contains("名前"));
    assert!(plain.contains("太郎"));
}

#[test]
fn format_error_with_unicode() {
    let e = format_error("无效输入");
    let plain = strip_ansi(&e);
    assert!(plain.contains("无效输入"));
}

#[test]
fn format_question_with_newlines_in_message() {
    // Messages with newlines should still produce output (even if odd)
    let q = format_question("line1\nline2", "");
    let plain = strip_ansi(&q);
    assert!(plain.contains("line1"));
    assert!(plain.contains("line2"));
}

#[test]
fn format_success_with_empty_strings() {
    let s = format_success("", "");
    let plain = strip_ansi(&s);
    // Should at least contain the success symbol
    assert!(plain.contains(DEFAULT_THEME.sym_success));
}

// =========================================================================
// 10. Property-based tests: rendering helpers never panic
// =========================================================================

proptest! {
    #[test]
    fn format_question_never_panics(
        message in "\\PC{0,200}",
        suffix in "\\PC{0,100}",
    ) {
        let result = format_question(&message, &suffix);
        // Should always contain RESET (well-formed output)
        prop_assert!(result.contains(RESET));
    }

    #[test]
    fn format_success_never_panics(
        message in "\\PC{0,200}",
        answer in "\\PC{0,200}",
    ) {
        let result = format_success(&message, &answer);
        prop_assert!(result.contains(RESET));
    }

    #[test]
    fn format_error_never_panics(msg in "\\PC{0,200}") {
        let result = format_error(&msg);
        prop_assert!(result.contains(RESET));
    }

    #[test]
    fn strip_ansi_never_panics(s in "\\PC{0,500}") {
        let _ = strip_ansi(&s);
    }

    #[test]
    fn ansi_color_arbitrary_input_no_panic(s in "\\PC{0,20}") {
        let _ = ansi_color(&s);
    }

    #[test]
    fn format_question_stripped_always_contains_colon(
        message in "[a-zA-Z0-9 ]{1,50}",
        suffix in "[a-zA-Z0-9() ]{0,30}",
    ) {
        let q = format_question(&message, &suffix);
        let plain = strip_ansi(&q);
        prop_assert!(
            plain.contains(':'),
            "Stripped format_question should always contain a colon: {plain:?}"
        );
    }

    #[test]
    fn format_success_stripped_contains_checkmark(
        message in "[a-zA-Z0-9 ]{1,50}",
        answer in "[a-zA-Z0-9 ]{0,50}",
    ) {
        let s = format_success(&message, &answer);
        let plain = strip_ansi(&s);
        prop_assert!(
            plain.contains(DEFAULT_THEME.sym_success),
            "Stripped format_success should contain checkmark: {plain:?}"
        );
    }

    /// Random choice lists used as rendering input should produce valid
    /// item tuples without panicking.
    #[test]
    fn choice_list_construction_random_no_panic(
        count in 1usize..100,
        has_separator in any::<bool>(),
    ) {
        let mut choices: Vec<ChoiceItem> = (0..count)
            .map(|i| ChoiceItem::Choice(Choice::new(format!("Item {i}"), json!(i))))
            .collect();
        if has_separator {
            choices.insert(0, ChoiceItem::Separator(Separator::new("---")));
        }
        // Simulate what select_terminal does: compute selectable indices
        let indices: Vec<usize> = choices.iter().enumerate().filter_map(|(i, c)| {
            match c {
                ChoiceItem::Choice(c) if !c.is_disabled() => Some(i),
                _ => None,
            }
        }).collect();
        prop_assert!(!indices.is_empty(), "Should always have selectable items");
    }

    /// validate_number with random f64 values should never panic.
    #[test]
    fn validate_number_random_no_panic(value in -1e6f64..1e6f64) {
        let config = NumberConfig {
            message: "x".into(),
            default: None,
            min: None,
            max: None,
            step: None,
            float_allowed: true,
            keep_input: true,
        };
        let _ = validate_number(&json!(value), &config);
    }

    /// validate_rawlist with random index should never panic.
    #[test]
    fn validate_rawlist_random_index_no_panic(idx in 0u64..1000) {
        let choices = vec![
            Choice::new("A", json!("a")),
            Choice::new("B", json!("b")),
        ];
        let _ = validate_rawlist(&json!(idx), &choices);
    }

    /// validate_expand with random string should never panic.
    #[test]
    fn validate_expand_random_no_panic(input in "\\PC{0,50}") {
        let choices = vec![
            ExpandChoice { key: "y".into(), name: "Yes".into(), value: json!(true) },
            ExpandChoice { key: "n".into(), name: "No".into(), value: json!(false) },
        ];
        let _ = validate_expand(&json!(input), &choices);
    }

    /// coerce_bool with arbitrary JSON should never panic.
    #[test]
    fn coerce_bool_random_no_panic(val in prop_oneof![
        any::<bool>().prop_map(|b| json!(b)),
        "\\PC{0,50}".prop_map(|s| json!(s)),
        any::<i64>().prop_map(|n| json!(n)),
        Just(json!(null)),
        Just(json!([])),
        Just(json!({})),
        any::<f64>().prop_filter("finite", |f| f.is_finite()).prop_map(|f| json!(f)),
    ]) {
        let _ = coerce_bool(&val);
    }
}
