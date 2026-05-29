use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Choice {
    pub name: String,
    pub value: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub disabled: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub short: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

impl Choice {
    pub fn new(name: impl Into<String>, value: impl Into<Value>) -> Self {
        Self {
            name: name.into(),
            value: value.into(),
            disabled: None,
            short: None,
            description: None,
        }
    }

    pub fn is_disabled(&self) -> bool {
        match &self.disabled {
            None => false,
            Some(Value::Bool(b)) => *b,
            Some(Value::String(s)) => !s.is_empty(),
            _ => true,
        }
    }

    pub fn disabled_reason(&self) -> Option<&str> {
        match &self.disabled {
            Some(Value::String(s)) => Some(s),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Separator {
    #[serde(rename = "type")]
    pub kind: String,
    pub text: String,
}

impl Separator {
    pub fn new(text: impl Into<String>) -> Self {
        Self {
            kind: "separator".to_string(),
            text: text.into(),
        }
    }
}

impl Default for Separator {
    fn default() -> Self {
        Self::new("────────")
    }
}

#[derive(Debug, Clone)]
pub enum ChoiceItem {
    Choice(Choice),
    Separator(Separator),
}

impl ChoiceItem {
    pub fn to_json(&self) -> Value {
        match self {
            Self::Choice(c) => serde_json::to_value(c).unwrap_or(Value::Null),
            Self::Separator(s) => serde_json::to_value(s).unwrap_or(Value::Null),
        }
    }
}

pub fn parse_choice(raw: &str) -> ChoiceItem {
    ChoiceItem::Choice(Choice::new(raw, Value::String(raw.to_string())))
}

pub fn parse_choice_from_value(val: Value) -> ChoiceItem {
    match &val {
        Value::String(s) => ChoiceItem::Choice(Choice::new(s.as_str(), val.clone())),
        Value::Object(map) => {
            if map.get("type").and_then(|v| v.as_str()) == Some("separator") {
                let text = map
                    .get("text")
                    .and_then(|v| v.as_str())
                    .unwrap_or("────────");
                ChoiceItem::Separator(Separator::new(text))
            } else {
                // Build the choice field-by-field so that a missing `value`
                // defaults to `name` (rather than stringifying the whole
                // object, which would never match an answer).
                let name = match map.get("name") {
                    Some(Value::String(s)) => s.clone(),
                    Some(other) => other.to_string(),
                    None => match map.get("value") {
                        Some(Value::String(s)) => s.clone(),
                        Some(other) => other.to_string(),
                        None => String::new(),
                    },
                };
                let value = map
                    .get("value")
                    .cloned()
                    .unwrap_or_else(|| Value::String(name.clone()));
                ChoiceItem::Choice(Choice {
                    name,
                    value,
                    disabled: map.get("disabled").cloned(),
                    short: map.get("short").and_then(|v| v.as_str()).map(String::from),
                    description: map
                        .get("description")
                        .and_then(|v| v.as_str())
                        .map(String::from),
                })
            }
        }
        _ => ChoiceItem::Choice(Choice::new(val.to_string(), val)),
    }
}
