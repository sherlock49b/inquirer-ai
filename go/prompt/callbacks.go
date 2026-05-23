package prompt

import "fmt"

func applyCallbacks(result any, validate func(any) error, filter func(any) any) (any, error) {
	if filter != nil {
		result = filter(result)
	}
	if validate != nil {
		if err := validate(result); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
}

func applyCallbacksList(result []any, validate func(any) error, filter func(any) any) ([]any, error) {
	if filter != nil {
		raw := filter(result)
		if filtered, ok := raw.([]any); ok {
			result = filtered
		}
	}
	if validate != nil {
		if err := validate(result); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	return result, nil
}
