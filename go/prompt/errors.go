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
