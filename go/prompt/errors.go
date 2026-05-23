package prompt

import (
	"errors"
	"fmt"
)

var (
	ErrAborted       = errors.New("prompt aborted")
	ErrValidation    = errors.New("validation failed")
	ErrInvalidChoice = errors.New("invalid choice")
	ErrInvalidJSON   = errors.New("invalid JSON response")
	ErrStdinClosed   = errors.New("stdin closed")
	ErrEditor        = errors.New("editor error")
)

type PromptError struct {
	PromptType string
	Message    string
	Err        error
}

func (e *PromptError) Error() string {
	return fmt.Sprintf("[%s] %q: %v", e.PromptType, e.Message, e.Err)
}

func (e *PromptError) Unwrap() error {
	return e.Err
}
