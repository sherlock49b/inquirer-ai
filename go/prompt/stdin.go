package prompt

import (
	"bufio"
	"os"
	"sync"
)

var (
	terminalScanner     *bufio.Scanner
	terminalScannerOnce sync.Once
)

func getTerminalScanner() *bufio.Scanner {
	terminalScannerOnce.Do(func() {
		terminalScanner = bufio.NewScanner(os.Stdin)
		terminalScanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	})
	return terminalScanner
}
