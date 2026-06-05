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

/// The `[start, end)` slice of items visible around `cursor` in a scrolling
/// list, shared by the select / checkbox prompts.
///
/// Centers the cursor in a window of `min(page_size, total)` rows, clamping so
/// it never runs off either end. Pure function so the scroll math is
/// unit-testable rather than duplicated inline in each `render_items`. Mirrors
/// Go `visibleRange` / Python `_visible_window` / TypeScript `visibleRange`;
/// the cross-language golden table pins them together.
pub(crate) fn visible_range(cursor: usize, total: usize, page_size: usize) -> (usize, usize) {
    let ps = page_size.min(total);
    let start = cursor.saturating_sub(ps / 2).min(total.saturating_sub(ps));
    (start, (start + ps).min(total))
}

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

#[cfg(test)]
mod tests {
    use super::visible_range;

    // The viewport scroll window that select / checkbox render around the
    // cursor. All four languages compute the same [start, end); the reference
    // is Go `visibleRange`. This golden table is replicated verbatim in
    // python/tests/test_cross_language_consistency.py,
    // typescript/tests/cross-language.test.ts and go/prompt/tui_boundary_test.go
    // — drift reddens whichever copy diverged. Oracle:
    // ps = min(page_size, total); start = clamp(cursor - ps/2, 0, total - ps).
    //
    // (cursor, total, page_size, expected_start, expected_end)
    const GOLDEN: &[(usize, usize, usize, usize, usize)] = &[
        (0, 3, 10, 0, 3),       // total < page_size: no scroll
        (2, 3, 10, 0, 3),       // total < page_size: centered cursor still no scroll
        (0, 10, 10, 0, 10),     // total == page_size
        (0, 20, 10, 0, 10),     // cursor at top
        (5, 20, 10, 0, 10),     // cursor == ps/2: still pinned to 0
        (6, 20, 10, 1, 11),     // first scroll — off-by-one sentinel
        (15, 20, 10, 10, 20),   // centered mid-list
        (19, 20, 10, 10, 20),   // near end: clamped to total - ps
        (5, 12, 3, 4, 7),       // odd page_size, 3/2 == 1
        (5, 12, 4, 3, 7),       // even page_size, 4/2 == 2
        (7, 10, 1, 7, 8),       // page_size == 1
        (99, 100, 10, 90, 100), // end clamp
        (50, 100, 10, 45, 55),  // mid large list
        (0, 0, 5, 0, 0),        // empty list (defensive: must not panic)
    ];

    #[test]
    fn visible_range_matches_golden_table() {
        for &(cursor, total, page_size, start, end) in GOLDEN {
            assert_eq!(
                visible_range(cursor, total, page_size),
                (start, end),
                "visible_range({cursor}, {total}, {page_size})"
            );
        }
    }

    #[test]
    fn visible_range_span_and_bounds() {
        // Span is min(page_size, total); the window stays within [0, total]
        // and a valid cursor is always inside it.
        for total in 0..25 {
            for &page_size in &[1usize, 3, 4, 10] {
                for cursor in 0..total.max(1) {
                    let (start, end) = visible_range(cursor, total, page_size);
                    assert!(start <= end && end <= total);
                    assert_eq!(end - start, page_size.min(total));
                    if total > 0 && cursor < total {
                        assert!(start <= cursor && cursor < end);
                    }
                }
            }
        }
    }
}
