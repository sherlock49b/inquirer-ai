package prompt

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"
)

const maxSocketRetries = 3

// maxAnswerLineBytes caps the size of a single answer line read from the
// socket. Lines exceeding this are rejected with a validation_error (R10).
const maxAnswerLineBytes = 1 << 20 // 1 MiB

// maxSunPath is the conventional sun_path length limit for AF_UNIX sockets.
const maxSunPath = 104

// SocketTransport handles prompt I/O over a Unix domain socket.
// Each prompt cycle accepts a new connection, sends the prompt,
// reads the answer, validates, and responds.
type SocketTransport struct {
	path     string
	listener net.Listener
	sigCh    chan os.Signal

	mu                  sync.Mutex
	stdoutHandshakeSent bool
	socketHandshakeSent bool
	step                int
	cleanedUp           bool
}

func defaultSocketPath() string {
	return fmt.Sprintf("/tmp/inquirer-ai-%d.sock", os.Getpid())
}

// validateSocketEnvPath enforces the constraints on an explicitly supplied
// INQUIRER_AI_SOCKET path (R10): non-empty absolute path, length < 104 bytes,
// and an existing parent directory.
func validateSocketEnvPath(path string) error {
	if path == "" {
		return fmt.Errorf("INQUIRER_AI_SOCKET must be a non-empty path")
	}
	if !filepath.IsAbs(path) {
		return fmt.Errorf("INQUIRER_AI_SOCKET must be an absolute path, got %q", path)
	}
	if len(path) >= maxSunPath {
		return fmt.Errorf("INQUIRER_AI_SOCKET path too long (%d bytes, limit %d)", len(path), maxSunPath)
	}
	parent := filepath.Dir(path)
	info, err := os.Stat(parent)
	if err != nil || !info.IsDir() {
		return fmt.Errorf("INQUIRER_AI_SOCKET parent directory does not exist: %q", parent)
	}
	return nil
}

// prepareSocketPath removes a stale socket at path. It NEVER follows symlinks
// and NEVER unlinks a non-socket: if path exists and is a socket, it is
// unlinked (stale cleanup); if it exists and is not a socket, an error is
// returned so we refuse to clobber it.
func prepareSocketPath(path string) error {
	info, err := os.Lstat(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return fmt.Errorf("failed to stat socket path %q: %w", path, err)
	}
	if info.Mode()&os.ModeSocket == 0 {
		return fmt.Errorf("refusing to use socket path %q: existing file is not a socket", path)
	}
	if err := os.Remove(path); err != nil {
		return fmt.Errorf("failed to remove stale socket %q: %w", path, err)
	}
	return nil
}

func newSocketTransport(path string) (*SocketTransport, error) {
	if path == "" {
		path = defaultSocketPath()
	} else if err := validateSocketEnvPath(path); err != nil {
		return nil, err
	}

	// Remove a stale socket, refusing to clobber a non-socket file.
	if err := prepareSocketPath(path); err != nil {
		return nil, err
	}

	listener, err := net.Listen("unix", path)
	if err != nil {
		return nil, fmt.Errorf("failed to create socket: %w", err)
	}

	// Restrict the socket to the owner.
	if err := os.Chmod(path, 0o600); err != nil {
		_ = listener.Close()
		_ = os.Remove(path)
		return nil, fmt.Errorf("failed to chmod socket %q: %w", path, err)
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
	t.mu.Lock()
	t.sigCh = ch
	t.mu.Unlock()
	go func() {
		if _, ok := <-ch; !ok {
			// Channel closed by Cleanup; exit the goroutine without acting.
			return
		}
		t.Cleanup()
		os.Exit(0)
	}()
}

// Cleanup closes the listener, removes the socket file, and stops the signal
// goroutine. It is idempotent and safe to call on every exit path (SIGINT,
// SIGTERM, and normal exit via a deferred call).
func (t *SocketTransport) Cleanup() {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.cleanedUp {
		return
	}
	t.cleanedUp = true

	// Stop receiving signals and release the goroutine: signal.Stop detaches
	// the channel, and closing it lets the waiting goroutine return.
	if t.sigCh != nil {
		signal.Stop(t.sigCh)
		close(t.sigCh)
		t.sigCh = nil
	}

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
	// Copy the caller's payload before injecting protocol fields so we never
	// mutate the map owned by the caller (R10).
	sendPayload := make(map[string]any, len(payload)+3)
	for k, v := range payload {
		sendPayload[k] = v
	}

	t.mu.Lock()
	t.step++
	sendPayload["step"] = t.step
	sendPayload["kind"] = "prompt"
	sendPayload["total"] = nil
	t.mu.Unlock()

	retriesUsed := 0

	for retriesUsed < maxSocketRetries {
		conn, err := t.listener.Accept()
		if err != nil {
			return nil, fmt.Errorf("%w: socket accept: %v", ErrAborted, err)
		}

		result, done, retries, err := t.handleConnection(conn, sendPayload, validate, retriesUsed)
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

	// Send handshake on first socket connection only. The "already sent" flag
	// is set ONLY after the handshake write succeeds (R10).
	t.mu.Lock()
	sendHandshakeOnSocket := !t.socketHandshakeSent
	t.mu.Unlock()

	if sendHandshakeOnSocket {
		if err := writeJSON(writer, t.handshakePayload()); err != nil {
			return nil, false, retriesUsed, nil // treat write error as peek
		}
		t.mu.Lock()
		t.socketHandshakeSent = true
		t.mu.Unlock()
	}

	// Send prompt.
	if err := writeJSON(writer, payload); err != nil {
		return nil, false, retriesUsed, nil // treat write error as peek
	}

	// Read answers with retry loop.
	for retriesUsed < maxSocketRetries {
		line, tooLong, err := readBoundedLine(reader, maxAnswerLineBytes)
		if err != nil && !tooLong {
			// Client disconnected without answering — peek.
			return nil, false, retriesUsed, nil
		}

		// A line that exceeds the cap is rejected with a validation_error and
		// consumes a retry (R10), rather than being parsed.
		if tooLong {
			retriesUsed++
			result, done, errOut := t.rejectAnswer(writer, retriesUsed, "Answer exceeds maximum size of 1048576 bytes", ErrValidation)
			if done {
				return result, true, retriesUsed, errOut
			}
			continue
		}

		line = trimRight(line)
		if line == "" {
			// Empty line — peek.
			return nil, false, retriesUsed, nil
		}

		// Parse JSON. Never crash on untrusted input — any decode error is a
		// retryable validation error.
		var resp map[string]any
		if perr := json.Unmarshal([]byte(line), &resp); perr != nil {
			retriesUsed++
			msg := fmt.Sprintf("Invalid JSON response: %s", perr.Error())
			result, done, errOut := t.rejectAnswer(writer, retriesUsed, msg, ErrInvalidJSON)
			if done {
				return result, true, retriesUsed, errOut
			}
			continue
		}

		// Skip a handshake_ack line and read the next one without consuming a
		// retry.
		if kind, _ := resp["kind"].(string); kind == "handshake_ack" {
			continue
		}

		// Require an object with an "answer" field.
		answer, ok := resp["answer"]
		if !ok {
			retriesUsed++
			msg := `Answer must be a JSON object with an "answer" field`
			result, done, errOut := t.rejectAnswer(writer, retriesUsed, msg, ErrInvalidJSON)
			if done {
				return result, true, retriesUsed, errOut
			}
			continue
		}

		// Validate the answer. A non-validation panic is converted to an error
		// by safeCallValidate and reported as a fatal error on exhaustion.
		result, verr := safeCallValidate(validate, answer)
		if verr != nil {
			retriesUsed++
			// Send the bare validation message (no sentinel wrapper prefix).
			res, done, errOut := t.rejectAnswer(writer, retriesUsed, AgentMessage(verr), verr)
			if done {
				return res, true, retriesUsed, errOut
			}
			continue
		}

		// Accepted. Compute the result first, then write {"status":"accepted"}
		// under suppressed errors so a broken pipe does not lose the validated
		// answer (R10).
		_ = writeJSON(writer, map[string]any{"status": "accepted"})
		return result, true, retriesUsed, nil
	}

	return nil, true, retriesUsed, fmt.Errorf("%w: maximum validation retries exceeded", ErrValidation)
}

// rejectAnswer sends a validation_error (retries remaining) or a fatal error
// (budget exhausted) for an invalid answer. It returns (result, done, err):
// when done is true the caller must return immediately with the fatal error;
// otherwise the caller continues the retry loop.
func (t *SocketTransport) rejectAnswer(writer *bufio.Writer, retriesUsed int, msg string, cause error) (result any, done bool, err error) {
	if retriesUsed >= maxSocketRetries {
		_ = writeJSON(writer, map[string]any{"kind": "error", "message": msg})
		if cause == nil {
			cause = ErrValidation
		}
		return nil, true, cause
	}
	_ = writeJSON(writer, map[string]any{"kind": "validation_error", "message": msg})
	return nil, false, nil
}

// readBoundedLine reads a single newline-terminated line from r, capping the
// accumulated bytes at limit. It returns (line, tooLong, err). When the limit
// is exceeded it drains the rest of the line (up to a hard ceiling) so the
// connection can continue, returns tooLong=true, and a nil error.
func readBoundedLine(r *bufio.Reader, limit int) (line string, tooLong bool, err error) {
	var buf []byte
	for {
		b, err := r.ReadByte()
		if err != nil {
			if len(buf) == 0 {
				return "", false, err
			}
			return string(buf), false, nil
		}
		if b == '\n' {
			return string(buf), false, nil
		}
		if len(buf) >= limit {
			// Drain the remainder of the over-long line and stop.
			drainLine(r)
			return "", true, nil
		}
		buf = append(buf, b)
	}
}

// drainLine consumes bytes from r up to and including the next newline, or a
// bounded number of bytes if no newline is found, so an over-long line does
// not stall subsequent reads.
func drainLine(r *bufio.Reader) {
	const drainCeiling = 16 << 20 // 16 MiB safety ceiling
	for i := 0; i < drainCeiling; i++ {
		b, err := r.ReadByte()
		if err != nil || b == '\n' {
			return
		}
	}
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

// SocketTransportError returns any error encountered while initializing the
// socket transport (e.g. a refused non-socket path or an invalid
// INQUIRER_AI_SOCKET). It triggers lazy initialization if needed.
func SocketTransportError() error {
	socketTransportOnce.Do(func() {
		socketTransport, socketTransportErr = initSocketTransport()
	})
	return socketTransportErr
}

// Cleanup tears down the active socket transport (if any), removing the socket
// file and stopping its signal handler. Go has no atexit, so callers that use
// agent/socket mode SHOULD `defer prompt.Cleanup()` in main so the socket file
// is removed on normal exit; SIGINT and SIGTERM are handled automatically.
func Cleanup() {
	if st := GetSocketTransport(); st != nil {
		st.Cleanup()
	}
}

func initSocketTransport() (*SocketTransport, error) {
	// Per R3: use the SOCKET transport iff socket_requested AND NOT
	// (TRANSPORT == "stdio"). A plain piped non-TTY with no MODE/SOCKET stays
	// on the STDIO agent transport (backwards compatible).
	if stringToLower(os.Getenv("INQUIRER_AI_MODE")) == "human" {
		return nil, nil
	}
	if !socketRequested() {
		return nil, nil
	}

	// INQUIRER_AI_TRANSPORT=stdio forces the stdio agent transport.
	if stringToLower(os.Getenv("INQUIRER_AI_TRANSPORT")) == "stdio" {
		return nil, nil
	}

	// Socket path: INQUIRER_AI_SOCKET if set, else /tmp/inquirer-ai-{pid}.sock.
	return newSocketTransport(os.Getenv("INQUIRER_AI_SOCKET"))
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
