use inquirer_ai::choice::{parse_choice, ChoiceItem};
use inquirer_ai::prompts::confirm::coerce_bool;
use inquirer_ai::prompts::number::{validate_number, NumberConfig};
use proptest::prelude::*;
use serde_json::{json, Value};

proptest! {
    #[test]
    fn choice_roundtrip(s in "[a-zA-Z0-9 ]{1,50}") {
        let item = parse_choice(&s);
        match item {
            ChoiceItem::Choice(c) => {
                prop_assert_eq!(&c.name, &s);
                prop_assert_eq!(c.value, Value::String(s));
            }
            _ => prop_assert!(false, "expected Choice"),
        }
    }

    #[test]
    fn coerce_bool_always_returns_bool(val in prop_oneof![
        any::<bool>().prop_map(|b| json!(b)),
        "[a-zA-Z]{0,10}".prop_map(|s| json!(s)),
        any::<i64>().prop_map(|n| json!(n)),
    ]) {
        let result = coerce_bool(&val);
        let _ = result; // just confirm it doesn't panic
    }

    #[test]
    fn number_bounds_respected(
        value in -1000i64..1000i64,
        min_val in -500i64..0i64,
        max_val in 0i64..500i64,
    ) {
        if min_val > max_val {
            return Ok(());
        }
        let config = NumberConfig {
            message: "x".into(),
            default: None,
            min: Some(min_val as f64),
            max: Some(max_val as f64),
            step: None,
            float_allowed: true,
            keep_input: true,
        };
        match validate_number(&json!(value), &config) {
            Ok(n) => {
                prop_assert!(n >= min_val as f64);
                prop_assert!(n <= max_val as f64);
            }
            Err(_) => {
                prop_assert!((value as f64) < min_val as f64 || (value as f64) > max_val as f64);
            }
        }
    }

    #[test]
    fn number_no_float_truncates(value in -1000i64..1000i64) {
        let config = NumberConfig {
            message: "x".into(),
            default: None,
            min: None,
            max: None,
            step: None,
            float_allowed: false,
            keep_input: true,
        };
        let result = validate_number(&json!(value), &config).unwrap();
        prop_assert_eq!(result, value as f64);
    }
}
