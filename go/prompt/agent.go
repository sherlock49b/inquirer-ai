package prompt

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
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

// version is read from version.go (single source, updated by cz bump)
var version = Version

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

// AgentSend advances the global logical-prompt step by one and emits the
// prompt frame at that step. Use it for a brand-new logical prompt. Validation
// re-sends of the SAME logical prompt must reuse the step value via
// agentSendAtStep so the "step" field is identical across a prompt and all of
// its retries (it must never exceed "total").
func AgentSend(payload map[string]any) error {
	agentStep++
	return agentSendAtStep(payload, agentStep)
}

// agentSendAtStep emits a prompt frame at an explicit logical step without
// advancing the global counter. It is used to re-send a prompt after a
// validation error so the re-send keeps the original step value.
func agentSendAtStep(payload map[string]any, step int) error {
	sendHandshake()
	payload["kind"] = "prompt"
	payload["step"] = step
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
			// EOF / closed stdin is an immediate fatal abort, not a retry.
			return nil, fmt.Errorf("%w: stdin closed", ErrAborted)
		}

		line := strings.TrimRight(scanner.Text(), "\r")
		// An empty / blank line is treated as EOF: immediate fatal abort, not a
		// retryable invalid-JSON error (R1).
		if strings.TrimSpace(line) == "" {
			return nil, fmt.Errorf("%w: empty answer line", ErrAborted)
		}

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
//
// If socket transport is active, the prompt cycle is handled over the Unix
// socket instead of stdin/stdout.
func AgentPromptWithRetry(payload map[string]any, validate func(any) (any, error)) (any, error) {
	// Check for socket transport first. If socket init failed (e.g. a refused
	// non-socket path or an invalid INQUIRER_AI_SOCKET), surface that error
	// rather than silently falling back to stdio.
	if st := GetSocketTransport(); st != nil {
		return st.PromptCycle(payload, validate)
	}
	if err := SocketTransportError(); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrPrompt, err)
	}

	// Single unified retry budget: 3 total answer attempts. Attempts 1 and 2
	// failing validation emit a validation_error; attempt 3 (or any receive
	// failure such as EOF / closed stdin / invalid JSON) emits a fatal
	// {"kind":"error"} and returns a non-nil error (R1, go-prompts-8).
	//
	// "step" is the 1-based LOGICAL prompt index: it advances ONCE per logical
	// prompt, and every validation re-send of that prompt reuses the same step
	// value so it never exceeds "total".
	const maxRetries = 3
	sendHandshake()
	agentStep++
	step := agentStep
	for attempt := 0; attempt < maxRetries; attempt++ {
		if err := agentSendAtStep(payload, step); err != nil {
			return nil, err
		}
		answer, err := AgentReceive()
		if err != nil {
			// EOF / closed stdin / malformed protocol line: immediate fatal
			// abort with a {"kind":"error"} message.
			_ = AgentSendError(AgentMessage(err))
			return nil, err
		}
		result, err := safeCallValidate(validate, answer)
		if err != nil {
			// The agent-facing message is the bare validation text (no
			// "prompt error: validation failed: " wrapper).
			if attempt < maxRetries-1 {
				_ = AgentSendValidationError(AgentMessage(err))
				continue
			}
			_ = AgentSendError(AgentMessage(err))
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

// safeCallValidate calls the validate function and recovers from panics,
// converting them to ErrValidation errors.
func safeCallValidate(validate func(any) (any, error), answer any) (result any, err error) {
	defer func() {
		if r := recover(); r != nil {
			switch v := r.(type) {
			case error:
				err = fmt.Errorf("%w: validator panicked: %v", ErrValidation, v)
			default:
				err = fmt.Errorf("%w: validator panicked: %v", ErrValidation, v)
			}
		}
	}()
	return validate(answer)
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
