pub mod autocomplete;
pub mod checkbox;
pub mod confirm;
pub mod editor;
pub mod expand;
pub mod number;
pub mod password;
pub mod path;
pub mod rawlist;
pub mod search;
pub mod select;
pub mod text;

use serde_json::Value;

/// Build the canonical invalid-choice validation message shared by the
/// select / checkbox / rawlist / expand prompts.
///
/// The format is byte-identical across all language implementations:
///
/// ```text
/// Invalid choice: <A>. Valid: [<V1>, <V2>, ...]
/// ```
///
/// where `<A>` is the rejected answer encoded as compact JSON and each `<Vi>`
/// is a valid value (or expand key) encoded as compact JSON, joined by `", "`.
pub(crate) fn invalid_choice_message<'a>(
    answer: &Value,
    valid: impl IntoIterator<Item = &'a Value>,
) -> String {
    let answer_str = serde_json::to_string(answer).unwrap_or_else(|_| "null".to_string());
    let valid_strs: Vec<String> = valid
        .into_iter()
        .map(|v| serde_json::to_string(v).unwrap_or_else(|_| "null".to_string()))
        .collect();
    format!(
        "Invalid choice: {answer_str}. Valid: [{}]",
        valid_strs.join(", ")
    )
}
