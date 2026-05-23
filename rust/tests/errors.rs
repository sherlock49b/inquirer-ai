use inquirer_ai::InquirerError;

#[test]
fn validation_error_displays() {
    let err = InquirerError::Validation("bad input".into());
    assert!(err.to_string().contains("bad input"));
}

#[test]
fn invalid_choice_displays() {
    let err = InquirerError::InvalidChoice("no such".into());
    assert!(err.to_string().contains("no such"));
}

#[test]
fn prompt_aborted_displays() {
    let err = InquirerError::PromptAborted("ctrl-c".into());
    assert!(err.to_string().contains("ctrl-c"));
}

#[test]
fn editor_error_displays() {
    let err = InquirerError::Editor("vi failed".into());
    assert!(err.to_string().contains("vi failed"));
}

#[test]
fn io_error_wraps() {
    let io_err = std::io::Error::new(std::io::ErrorKind::BrokenPipe, "broken");
    let err = InquirerError::from(io_err);
    assert!(err.to_string().contains("broken"));
    assert!(matches!(err, InquirerError::Io(_)));
}

#[test]
fn json_error_wraps() {
    let json_err = serde_json::from_str::<serde_json::Value>("not json").unwrap_err();
    let err = InquirerError::from(json_err);
    assert!(err.to_string().contains("Invalid JSON"));
}

#[test]
fn error_is_std_error() {
    let err = InquirerError::Validation("test".into());
    let _: &dyn std::error::Error = &err;
}
