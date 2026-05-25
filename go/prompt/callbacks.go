package prompt

import "fmt"

func applyCallbacks(result any, validate func(any) error, filter func(any) any) (final any, err error) {
	defer func() {
		if r := recover(); r != nil {
			switch v := r.(type) {
			case error:
				err = fmt.Errorf("%w: validator panicked: %v", ErrValidation, v)
			default:
				err = fmt.Errorf("%w: validator panicked: %v", ErrValidation, v)
			}
			final = nil
		}
	}()
	if validate != nil {
		if err := validate(result); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	if filter != nil {
		result = filter(result)
	}
	return result, nil
}

func applyCallbacksList(result []any, validate func(any) error, filter func(any) any) (final []any, err error) {
	defer func() {
		if r := recover(); r != nil {
			switch v := r.(type) {
			case error:
				err = fmt.Errorf("%w: validator panicked: %v", ErrValidation, v)
			default:
				err = fmt.Errorf("%w: validator panicked: %v", ErrValidation, v)
			}
			final = nil
		}
	}()
	if validate != nil {
		if err := validate(result); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrValidation, err)
		}
	}
	if filter != nil {
		raw := filter(result)
		if filtered, ok := raw.([]any); ok {
			result = filtered
		}
	}
	return result, nil
}
