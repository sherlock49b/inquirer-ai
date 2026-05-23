package prompt

import "errors"

var (
	ErrAborted       = errors.New("prompt aborted")
	ErrValidation    = errors.New("validation failed")
	ErrInvalidChoice = errors.New("invalid choice")
	ErrInvalidJSON   = errors.New("invalid JSON response")
	ErrStdinClosed   = errors.New("stdin closed")
	ErrEditor        = errors.New("editor error")
)
