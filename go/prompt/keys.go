package prompt

import (
	"os"

	"golang.org/x/term"
)

const (
	keyUp    = "up"
	keyDown  = "down"
	keyEnter = "enter"
	keySpace = "space"
	keyCtrlC = "ctrl-c"
	keyOther = ""
)

func readKey() (string, error) {
	oldState, err := term.MakeRaw(int(os.Stdin.Fd()))
	if err != nil {
		return "", err
	}
	defer term.Restore(int(os.Stdin.Fd()), oldState)

	buf := make([]byte, 3)
	n, err := os.Stdin.Read(buf)
	if err != nil {
		return "", err
	}

	if n == 1 {
		switch buf[0] {
		case 13, 10:
			return keyEnter, nil
		case 3:
			return keyCtrlC, nil
		case 32:
			return keySpace, nil
		case 'k':
			return keyUp, nil
		case 'j':
			return keyDown, nil
		}
	}

	if n == 3 && buf[0] == 27 && buf[1] == 91 {
		switch buf[2] {
		case 65:
			return keyUp, nil
		case 66:
			return keyDown, nil
		}
	}

	return keyOther, nil
}
