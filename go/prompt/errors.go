package prompt

import (
	"errors"
	"fmt"
)

// Sentinel errors form a hierarchy via wrapping.
// Use errors.Is() to match — e.g., errors.Is(err, ErrValidation) catches
// both direct validation errors and ErrInvalidChoice.
//
//	ErrPrompt (base)
//	├── ErrAborted (user cancelled or stdin closed)
//	├── ErrValidation (input failed validation)
//	│   └── ErrInvalidChoice (choice not in list / disabled)
//	├── ErrInvalidJSON (malformed agent protocol input)
//	└── ErrEditor (editor subprocess failed)

var (
	ErrPrompt        = errors.New("prompt error")
	ErrAborted       = fmt.Errorf("%w: aborted", ErrPrompt)
	ErrValidation    = fmt.Errorf("%w: validation failed", ErrPrompt)
	ErrInvalidChoice = fmt.Errorf("%w: invalid choice", ErrValidation)
	ErrInvalidJSON   = fmt.Errorf("%w: invalid JSON response", ErrPrompt)
	ErrEditor        = fmt.Errorf("%w: editor error", ErrPrompt)
)

// validationError carries a clean, agent-facing message alongside a wrapped
// sentinel chain. errors.Is(err, ErrValidation) / ErrInvalidChoice still work
// (the sentinel is wrapped via cause), while AgentMessage returns the bare,
// canonical message that is sent in the {"kind":"validation_error"} frame —
// without the "prompt error: validation failed: ..." sentinel prefix.
type validationError struct {
	msg   string // canonical, agent-facing message (no wrapper prefix)
	cause error  // sentinel chain for errors.Is (e.g. ErrInvalidChoice)
}

func (e *validationError) Error() string { return e.msg }
func (e *validationError) Unwrap() error { return e.cause }

// newValidationError builds a validationError with a clean agent-facing message
// and the given sentinel cause (used for errors.Is matching).
func newValidationError(cause error, msg string) error {
	return &validationError{msg: msg, cause: cause}
}

// AgentMessage returns the bare message that should be sent to the agent in a
// validation_error / error frame for err. For a validationError it is the
// clean canonical message. For any other error it is err.Error() with the
// known sentinel wrapper prefixes stripped, so messages like
// "Decimal numbers are not allowed" are sent without the
// "prompt error: validation failed: " framing.
func AgentMessage(err error) string {
	if err == nil {
		return ""
	}
	var ve *validationError
	if errors.As(err, &ve) {
		return ve.msg
	}
	return stripValidationWrapper(err.Error())
}

// validationWrapperPrefixes are the sentinel-derived framing prefixes that must
// not appear in the agent-facing validation message. They mirror the
// conformance harness's known wrapper prefixes.
var validationWrapperPrefixes = []string{
	"prompt error: validation failed: ",
	"validation failed: ",
}

// stripValidationWrapper removes any leading sentinel framing prefix(es) from
// msg so the bare underlying validation text is sent to the agent.
func stripValidationWrapper(msg string) string {
	for {
		stripped := false
		for _, p := range validationWrapperPrefixes {
			if len(msg) >= len(p) && msg[:len(p)] == p {
				msg = msg[len(p):]
				stripped = true
			}
		}
		if !stripped {
			return msg
		}
	}
}
