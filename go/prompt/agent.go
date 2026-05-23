package prompt

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"sync"
)

var (
	handshakeOnce sync.Once
	stdinScanner  *bufio.Scanner
	scannerOnce   sync.Once
)

const version = "0.1.0"

func sendHandshake() {
	handshakeOnce.Do(func() {
		meta := map[string]any{
			"protocol":         "inquirer-ai",
			"version":          version,
			"format":           "jsonl",
			"description":      "Each prompt is a JSON line on stdout. Respond with a JSON line on stdin.",
			"example_response": map[string]any{"answer": "<value>"},
		}
		data, _ := json.Marshal(meta)
		fmt.Fprintln(os.Stdout, string(data))
	})
}

func getScanner() *bufio.Scanner {
	scannerOnce.Do(func() {
		stdinScanner = bufio.NewScanner(os.Stdin)
		stdinScanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	})
	return stdinScanner
}

func AgentSend(payload map[string]any) error {
	sendHandshake()
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintln(os.Stdout, string(data))
	return err
}

func AgentReceive() (any, error) {
	scanner := getScanner()
	if !scanner.Scan() {
		if err := scanner.Err(); err != nil {
			return nil, fmt.Errorf("%w: %v", ErrStdinClosed, err)
		}
		return nil, ErrStdinClosed
	}

	line := scanner.Text()
	var resp map[string]any
	if err := json.Unmarshal([]byte(line), &resp); err != nil {
		return nil, fmt.Errorf("%w: %v. Expected JSON like: {\"answer\": \"<value>\"}", ErrInvalidJSON, err)
	}

	answer, ok := resp["answer"]
	if !ok {
		return nil, fmt.Errorf("%w: response must have an \"answer\" key", ErrInvalidJSON)
	}
	return answer, nil
}
