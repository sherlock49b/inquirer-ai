package prompt

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/signal"
	"sync"
	"syscall"
)

const maxSocketRetries = 3

// SocketTransport handles prompt I/O over a Unix domain socket.
// Each prompt cycle accepts a new connection, sends the prompt,
// reads the answer, validates, and responds.
type SocketTransport struct {
	path     string
	listener net.Listener

	mu                  sync.Mutex
	stdoutHandshakeSent bool
	socketHandshakeSent bool
	step                int
	cleanedUp           bool
}

func defaultSocketPath() string {
	return fmt.Sprintf("/tmp/inquirer-ai-%d.sock", os.Getpid())
}

func newSocketTransport(path string) (*SocketTransport, error) {
	if path == "" {
		path = defaultSocketPath()
	}

	// Remove stale socket file if it exists.
	if _, err := os.Stat(path); err == nil {
		os.Remove(path)
	}

	listener, err := net.Listen("unix", path)
	if err != nil {
		return nil, fmt.Errorf("failed to create socket: %w", err)
	}

	t := &SocketTransport{
		path:     path,
		listener: listener,
	}

	t.sendStdoutHandshake()
	t.installCleanupHandlers()

	return t, nil
}

func (t *SocketTransport) installCleanupHandlers() {
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		<-ch
		t.Cleanup()
		os.Exit(0)
	}()
}

// Cleanup closes the listener and removes the socket file.
func (t *SocketTransport) Cleanup() {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.cleanedUp {
		return
	}
	t.cleanedUp = true

	if t.listener != nil {
		t.listener.Close()
	}
	os.Remove(t.path)
}

func (t *SocketTransport) sendStdoutHandshake() {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.stdoutHandshakeSent {
		return
	}
	t.stdoutHandshakeSent = true
	payload := t.handshakePayload()
	data, _ := json.Marshal(payload)
	fmt.Fprintln(os.Stdout, string(data))
}

func (t *SocketTransport) handshakePayload() map[string]any {
	return map[string]any{
		"kind":        "handshake",
		"protocol":    "inquirer-ai",
		"version":     version,
		"format":      "jsonl",
		"socket":      t.path,
		"interaction": "sequential",
		"total":       nil,
		"description": "Interactive prompt protocol over Unix socket. " +
			"Connect to read a prompt, send a JSON answer, receive status. " +
			"One connection per prompt.",
		"example_response": map[string]any{"answer": "<value>"},
	}
}

// PromptCycle handles a full prompt cycle over the socket:
// accept connection, send prompt, read answer, validate, respond.
// It supports peek (disconnect without answer) and validation retry.
func (t *SocketTransport) PromptCycle(payload map[string]any, validate func(any) (any, error)) (any, error) {
	t.mu.Lock()
	t.step++
	payload["step"] = t.step
	payload["kind"] = "prompt"
	payload["total"] = nil
	t.mu.Unlock()

	retriesUsed := 0

	for retriesUsed < maxSocketRetries {
		conn, err := t.listener.Accept()
		if err != nil {
			return nil, fmt.Errorf("%w: socket accept: %v", ErrAborted, err)
		}

		result, done, retries, err := t.handleConnection(conn, payload, validate, retriesUsed)
		retriesUsed = retries
		if err != nil {
			return nil, err
		}
		if done {
			return result, nil
		}
		// Not done means peek (client disconnected without answering), loop to accept again.
	}

	return nil, fmt.Errorf("%w: maximum validation retries exceeded", ErrValidation)
}

// handleConnection processes a single socket connection for a prompt cycle.
// Returns (result, done, retriesUsed, error).
// done=false means the client disconnected without answering (peek).
func (t *SocketTransport) handleConnection(
	conn net.Conn,
	payload map[string]any,
	validate func(any) (any, error),
	retriesUsed int,
) (any, bool, int, error) {
	defer conn.Close()

	reader := bufio.NewReader(conn)
	writer := bufio.NewWriter(conn)

	// Send handshake on first socket connection only.
	t.mu.Lock()
	sendHandshakeOnSocket := !t.socketHandshakeSent
	if sendHandshakeOnSocket {
		t.socketHandshakeSent = true
	}
	t.mu.Unlock()

	if sendHandshakeOnSocket {
		if err := writeJSON(writer, t.handshakePayload()); err != nil {
			return nil, false, retriesUsed, nil // treat write error as peek
		}
	}

	// Send prompt.
	if err := writeJSON(writer, payload); err != nil {
		return nil, false, retriesUsed, nil // treat write error as peek
	}

	// Read answers with retry loop.
	for retriesUsed < maxSocketRetries {
		line, err := reader.ReadString('\n')
		if err != nil || len(line) == 0 || line == "\n" {
			// Client disconnected without answering — peek.
			return nil, false, retriesUsed, nil
		}

		line = trimRight(line)
		if line == "" {
			// Empty line after trimming — peek.
			return nil, false, retriesUsed, nil
		}

		// Parse JSON.
		var resp map[string]any
		if err := json.Unmarshal([]byte(line), &resp); err != nil {
			retriesUsed++
			msg := fmt.Sprintf("Invalid JSON: %s", line)
			if retriesUsed >= maxSocketRetries {
				writeJSON(writer, map[string]any{"kind": "error", "message": msg})
				return nil, true, retriesUsed, fmt.Errorf("%w: %s", ErrInvalidJSON, msg)
			}
			writeJSON(writer, map[string]any{"kind": "validation_error", "message": msg})
			continue
		}

		// Skip handshake_ack.
		if kind, _ := resp["kind"].(string); kind == "handshake_ack" {
			line2, err := reader.ReadString('\n')
			if err != nil || len(line2) == 0 || line2 == "\n" {
				return nil, false, retriesUsed, nil
			}
			line2 = trimRight(line2)
			if line2 == "" {
				return nil, false, retriesUsed, nil
			}
			resp = nil
			if err := json.Unmarshal([]byte(line2), &resp); err != nil {
				retriesUsed++
				msg := fmt.Sprintf("Invalid JSON: %s", line2)
				if retriesUsed >= maxSocketRetries {
					writeJSON(writer, map[string]any{"kind": "error", "message": msg})
					return nil, true, retriesUsed, fmt.Errorf("%w: %s", ErrInvalidJSON, msg)
				}
				writeJSON(writer, map[string]any{"kind": "validation_error", "message": msg})
				continue
			}
		}

		// Check for "answer" key.
		answer, ok := resp["answer"]
		if !ok {
			retriesUsed++
			msg := `Response must be a JSON object with an "answer" key`
			if retriesUsed >= maxSocketRetries {
				writeJSON(writer, map[string]any{"kind": "error", "message": msg})
				return nil, true, retriesUsed, fmt.Errorf("%w: %s", ErrInvalidJSON, msg)
			}
			writeJSON(writer, map[string]any{"kind": "validation_error", "message": msg})
			continue
		}

		// Validate the answer.
		result, err := safeCallValidate(validate, answer)
		if err != nil {
			retriesUsed++
			if retriesUsed >= maxSocketRetries {
				writeJSON(writer, map[string]any{"kind": "error", "message": err.Error()})
				return nil, true, retriesUsed, err
			}
			writeJSON(writer, map[string]any{"kind": "validation_error", "message": err.Error()})
			continue
		}

		// Accepted.
		writeJSON(writer, map[string]any{"status": "accepted"})
		return result, true, retriesUsed, nil
	}

	return nil, true, retriesUsed, fmt.Errorf("%w: maximum validation retries exceeded", ErrValidation)
}

func writeJSON(w *bufio.Writer, data map[string]any) error {
	b, err := json.Marshal(data)
	if err != nil {
		return err
	}
	_, err = w.Write(append(b, '\n'))
	if err != nil {
		return err
	}
	return w.Flush()
}

func trimRight(s string) string {
	// Trim trailing newline and carriage return.
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r') {
		s = s[:len(s)-1]
	}
	return s
}

// Package-level singleton for socket transport.
var (
	socketTransport     *SocketTransport
	socketTransportOnce sync.Once
	socketTransportErr  error
)

// GetSocketTransport returns the singleton SocketTransport if socket mode
// is active, or nil if not. Thread-safe via sync.Once.
func GetSocketTransport() *SocketTransport {
	socketTransportOnce.Do(func() {
		socketTransport, socketTransportErr = initSocketTransport()
	})
	return socketTransport
}

func initSocketTransport() (*SocketTransport, error) {
	envMode := os.Getenv("INQUIRER_AI_MODE")
	if stringToLower(envMode) == "human" {
		return nil, nil
	}

	// INQUIRER_AI_TRANSPORT=stdio skips socket creation (for backward-compatible tests).
	if stringToLower(os.Getenv("INQUIRER_AI_TRANSPORT")) == "stdio" {
		return nil, nil
	}

	// If INQUIRER_AI_SOCKET is set, use that path.
	if path := os.Getenv("INQUIRER_AI_SOCKET"); path != "" {
		return newSocketTransport(path)
	}

	// Auto-create socket in agent mode.
	if IsAgentMode() {
		return newSocketTransport("")
	}

	return nil, nil
}

func stringToLower(s string) string {
	// Simple lowercase for ASCII env var values.
	b := make([]byte, len(s))
	for i := range s {
		c := s[i]
		if c >= 'A' && c <= 'Z' {
			c += 'a' - 'A'
		}
		b[i] = c
	}
	return string(b)
}

// ResetSocketTransport cleans up and resets the singleton. Used for testing.
func ResetSocketTransport() {
	if socketTransport != nil {
		socketTransport.Cleanup()
	}
	socketTransport = nil
	socketTransportErr = nil
	socketTransportOnce = sync.Once{}
}
