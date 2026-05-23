package prompt

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"sync"
)

var (
	handshakeOnce sync.Once
	stdinScanner  *bufio.Scanner
	scannerOnce   sync.Once
	agentStep     int
	agentWriter   *os.File
	agentReader   *os.File
	agentIOOnce   sync.Once
)

const version = "0.2.0"

// initAgentIO sets up the writer and reader used for agent protocol I/O.
// If INQUIRER_AI_FD_OUT / INQUIRER_AI_FD_IN are set, those file descriptors
// are used; otherwise os.Stdout / os.Stdin.
func initAgentIO() {
	agentIOOnce.Do(func() {
		agentWriter = os.Stdout
		agentReader = os.Stdin

		if fdStr := os.Getenv("INQUIRER_AI_FD_OUT"); fdStr != "" {
			if fd, err := strconv.Atoi(fdStr); err == nil {
				agentWriter = os.NewFile(uintptr(fd), "agent-out")
			}
		}
		if fdStr := os.Getenv("INQUIRER_AI_FD_IN"); fdStr != "" {
			if fd, err := strconv.Atoi(fdStr); err == nil {
				agentReader = os.NewFile(uintptr(fd), "agent-in")
			}
		}
	})
}

func sendHandshake() {
	handshakeOnce.Do(func() {
		initAgentIO()
		meta := map[string]any{
			"kind":             "handshake",
			"protocol":         "inquirer-ai",
			"version":          version,
			"format":           "jsonl",
			"interaction":      "sequential",
			"total":            nil,
			"description":      "Interactive prompt protocol. Prompts are sent one at a time — read one JSON line from stdout, respond with one JSON line on stdin, then wait for the next prompt. Do NOT send all answers at once. Use a named pipe (mkfifo) or line-buffered I/O for bidirectional communication.",
			"example_response": map[string]any{"answer": "<value>"},
		}
		data, _ := json.Marshal(meta)
		fmt.Fprintln(agentWriter, string(data))
	})
}

func getScanner() *bufio.Scanner {
	scannerOnce.Do(func() {
		initAgentIO()
		stdinScanner = bufio.NewScanner(agentReader)
		stdinScanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	})
	return stdinScanner
}

func AgentSend(payload map[string]any) error {
	sendHandshake()
	agentStep++
	payload["kind"] = "prompt"
	payload["step"] = agentStep
	payload["total"] = nil
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintln(agentWriter, string(data))
	return err
}

func AgentReceive() (any, error) {
	scanner := getScanner()
	for {
		if !scanner.Scan() {
			if err := scanner.Err(); err != nil {
				return nil, fmt.Errorf("%w: stdin: %v", ErrAborted, err)
			}
			return nil, fmt.Errorf("%w: stdin closed", ErrAborted)
		}

		line := scanner.Text()
		var resp map[string]any
		if err := json.Unmarshal([]byte(line), &resp); err != nil {
			return nil, fmt.Errorf("%w: %v. Expected JSON like: {\"answer\": \"<value>\"}", ErrInvalidJSON, err)
		}

		if kind, _ := resp["kind"].(string); kind == "handshake_ack" {
			continue
		}

		answer, ok := resp["answer"]
		if !ok {
			return nil, fmt.Errorf("%w: response must have an \"answer\" key", ErrInvalidJSON)
		}
		return answer, nil
	}
}

// AgentPromptWithRetry sends a prompt payload to the agent and retries on
// validation errors up to 3 times total. The validate function receives the
// raw answer from the agent and should return the processed result or an error.
// On error the helper sends a validation-error message and re-sends the prompt.
func AgentPromptWithRetry(payload map[string]any, validate func(any) (any, error)) (any, error) {
	const maxRetries = 3
	for attempt := 0; attempt < maxRetries; attempt++ {
		if err := AgentSend(payload); err != nil {
			return nil, err
		}
		answer, err := AgentReceive()
		if err != nil {
			return nil, err
		}
		result, err := validate(answer)
		if err != nil {
			if attempt < maxRetries-1 {
				AgentSendValidationError(err.Error())
				continue
			}
			return nil, err
		}
		return result, nil
	}
	return nil, fmt.Errorf("%w: max retries exceeded", ErrValidation)
}

// AgentSendValidationError sends a validation error message to the agent.
func AgentSendValidationError(msg string) error {
	initAgentIO()
	payload := map[string]any{
		"kind":    "validation_error",
		"message": msg,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintln(agentWriter, string(data))
	return err
}

// AgentSendError sends a general error message to the agent.
func AgentSendError(msg string) error {
	initAgentIO()
	payload := map[string]any{
		"kind":    "error",
		"message": msg,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintln(agentWriter, string(data))
	return err
}
