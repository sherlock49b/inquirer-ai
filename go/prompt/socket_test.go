package prompt_test

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// waitForSocket polls until the socket file exists, up to timeout.
func waitForSocket(t *testing.T, path string, timeout time.Duration) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if _, err := os.Stat(path); err == nil {
			return
		}
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatalf("socket %s not created within %v", path, timeout)
}

// connectSocket connects to the Unix socket and returns the connection
// and buffered reader/writer.
func connectSocket(t *testing.T, path string) (net.Conn, *bufio.Reader, *bufio.Writer) {
	t.Helper()
	conn, err := net.Dial("unix", path)
	if err != nil {
		t.Fatalf("failed to connect to socket %s: %v", path, err)
	}
	conn.SetDeadline(time.Now().Add(5 * time.Second))
	return conn, bufio.NewReader(conn), bufio.NewWriter(conn)
}

// readUntilPrompt reads JSON lines from the socket until a "prompt" message is found.
func readUntilPrompt(t *testing.T, reader *bufio.Reader) []map[string]any {
	t.Helper()
	var messages []map[string]any
	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			t.Fatalf("reading from socket: %v", err)
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var msg map[string]any
		if err := json.Unmarshal([]byte(line), &msg); err != nil {
			t.Fatalf("invalid JSON from socket: %v\nline: %s", err, line)
		}
		messages = append(messages, msg)
		if kind, _ := msg["kind"].(string); kind == "prompt" {
			break
		}
	}
	return messages
}

// sendAnswer writes an answer JSON object and reads the response.
func sendAnswer(t *testing.T, writer *bufio.Writer, reader *bufio.Reader, answer any) map[string]any {
	t.Helper()
	data, err := json.Marshal(map[string]any{"answer": answer})
	if err != nil {
		t.Fatalf("marshal answer: %v", err)
	}
	_, err = writer.Write(append(data, '\n'))
	if err != nil {
		t.Fatalf("write answer: %v", err)
	}
	if err := writer.Flush(); err != nil {
		t.Fatalf("flush answer: %v", err)
	}

	line, err := reader.ReadString('\n')
	if err != nil {
		t.Fatalf("read response: %v", err)
	}
	var resp map[string]any
	if err := json.Unmarshal([]byte(strings.TrimSpace(line)), &resp); err != nil {
		t.Fatalf("invalid JSON response: %v\nline: %s", err, line)
	}
	return resp
}

// readStdoutHandshake reads the first JSON line from an io.Reader (stdout pipe).
func readStdoutHandshake(t *testing.T, stdout io.Reader) map[string]any {
	t.Helper()
	reader := bufio.NewReader(stdout)
	line, err := reader.ReadString('\n')
	if err != nil {
		t.Fatalf("failed to read handshake from stdout: %v", err)
	}
	var hs map[string]any
	if err := json.Unmarshal([]byte(strings.TrimSpace(line)), &hs); err != nil {
		t.Fatalf("invalid handshake JSON: %v\nline: %s", err, line)
	}
	return hs
}

// buildSocketTestProgram compiles a Go test helper program.
// The source must be in go/prompt/testdata/socket_<name>/main.go.
func buildSocketTestProgram(t *testing.T, name string) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	goDir := filepath.Dir(wd) // go/ directory

	tmpDir := t.TempDir()
	bin := filepath.Join(tmpDir, name)

	cmd := exec.Command("go", "build", "-o", bin, fmt.Sprintf("./prompt/testdata/socket_%s/", name))
	cmd.Dir = goDir
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("failed to build socket test program %s: %v\n%s", name, err, out)
	}
	return bin
}

func TestSocketBasicTextPrompt(t *testing.T) {
	bin := buildSocketTestProgram(t, "text")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}

	var stderrBuf bytes.Buffer
	cmd.Stderr = &stderrBuf
	stdoutPipe, _ := cmd.StdoutPipe()

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	// Read stdout handshake
	hs := readStdoutHandshake(t, stdoutPipe)
	if hs["protocol"] != "inquirer-ai" {
		t.Fatalf("expected protocol=inquirer-ai, got %v", hs["protocol"])
	}
	if hs["socket"] != sockPath {
		t.Fatalf("expected socket=%s, got %v", sockPath, hs["socket"])
	}

	conn, reader, writer := connectSocket(t, sockPath)

	msgs := readUntilPrompt(t, reader)
	// First connection: handshake + prompt
	if len(msgs) < 2 {
		t.Fatalf("expected at least 2 messages (handshake + prompt), got %d", len(msgs))
	}
	if msgs[0]["kind"] != "handshake" {
		t.Fatalf("expected first socket message to be handshake, got %v", msgs[0]["kind"])
	}
	if msgs[1]["kind"] != "prompt" {
		t.Fatalf("expected second message to be prompt, got %v", msgs[1]["kind"])
	}
	if msgs[1]["type"] != "input" {
		t.Fatalf("expected type=input, got %v", msgs[1]["type"])
	}
	if msgs[1]["message"] != "Name?" {
		t.Fatalf("expected message=Name?, got %v", msgs[1]["message"])
	}

	resp := sendAnswer(t, writer, reader, "Alice")
	if resp["status"] != "accepted" {
		t.Fatalf("expected status=accepted, got %v", resp)
	}
	conn.Close()

	cmd.Wait()
	if !strings.Contains(stderrBuf.String(), "RESULT:Alice") {
		t.Fatalf("expected RESULT:Alice in stderr, got: %s", stderrBuf.String())
	}
}

func TestSocketPeekThenAnswer(t *testing.T) {
	bin := buildSocketTestProgram(t, "text")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}

	var stderrBuf bytes.Buffer
	cmd.Stderr = &stderrBuf
	// Discard stdout (we don't need it for this test, but the program writes handshake there)
	cmd.Stdout = &bytes.Buffer{}

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	// Peek: connect and read prompt, then disconnect without answering.
	conn1, reader1, _ := connectSocket(t, sockPath)
	msgs1 := readUntilPrompt(t, reader1)
	if msgs1[len(msgs1)-1]["kind"] != "prompt" {
		t.Fatalf("expected prompt, got %v", msgs1[len(msgs1)-1]["kind"])
	}
	conn1.Close()

	// Second connection should get the same prompt (re-queued), but no handshake.
	conn2, reader2, writer2 := connectSocket(t, sockPath)

	msgs2 := readUntilPrompt(t, reader2)
	if len(msgs2) != 1 {
		t.Fatalf("expected 1 message (prompt only, no handshake), got %d: %v", len(msgs2), msgs2)
	}
	if msgs2[0]["kind"] != "prompt" {
		t.Fatalf("expected prompt, got %v", msgs2[0]["kind"])
	}
	if msgs2[0]["message"] != "Name?" {
		t.Fatalf("expected message=Name?, got %v", msgs2[0]["message"])
	}

	resp := sendAnswer(t, writer2, reader2, "Bob")
	if resp["status"] != "accepted" {
		t.Fatalf("expected accepted, got %v", resp)
	}
	conn2.Close()

	cmd.Wait()
	if !strings.Contains(stderrBuf.String(), "RESULT:Bob") {
		t.Fatalf("expected RESULT:Bob in stderr, got: %s", stderrBuf.String())
	}
}

func TestSocketValidationRetry(t *testing.T) {
	bin := buildSocketTestProgram(t, "number")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}

	var stderrBuf bytes.Buffer
	cmd.Stderr = &stderrBuf
	cmd.Stdout = &bytes.Buffer{}

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	conn, reader, writer := connectSocket(t, sockPath)

	readUntilPrompt(t, reader)

	// Send invalid number (below min).
	resp := sendAnswer(t, writer, reader, 80)
	if resp["kind"] != "validation_error" {
		t.Fatalf("expected validation_error, got %v", resp)
	}
	msg, _ := resp["message"].(string)
	if !strings.Contains(msg, "1024") {
		t.Fatalf("expected error about min 1024, got: %s", msg)
	}

	// Send valid number.
	resp = sendAnswer(t, writer, reader, 8080)
	if resp["status"] != "accepted" {
		t.Fatalf("expected accepted, got %v", resp)
	}
	conn.Close()

	cmd.Wait()
	if !strings.Contains(stderrBuf.String(), "RESULT:8080") {
		t.Fatalf("expected RESULT:8080 in stderr, got: %s", stderrBuf.String())
	}
}

func TestSocketMultiPromptSequence(t *testing.T) {
	bin := buildSocketTestProgram(t, "multi")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}

	var stderrBuf bytes.Buffer
	cmd.Stderr = &stderrBuf
	cmd.Stdout = &bytes.Buffer{}

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	// First prompt: text input.
	conn1, reader1, writer1 := connectSocket(t, sockPath)
	msgs := readUntilPrompt(t, reader1)
	if msgs[len(msgs)-1]["type"] != "input" {
		t.Fatalf("expected input prompt, got %v", msgs[len(msgs)-1]["type"])
	}
	step1, _ := msgs[len(msgs)-1]["step"].(float64)
	if step1 != 1 {
		t.Fatalf("expected step=1, got %v", step1)
	}
	resp := sendAnswer(t, writer1, reader1, "Charlie")
	if resp["status"] != "accepted" {
		t.Fatalf("expected accepted, got %v", resp)
	}
	conn1.Close()

	// Second prompt: confirm.
	conn2, reader2, writer2 := connectSocket(t, sockPath)
	msgs = readUntilPrompt(t, reader2)
	if msgs[0]["type"] != "confirm" {
		t.Fatalf("expected confirm prompt, got %v", msgs[0]["type"])
	}
	step2, _ := msgs[0]["step"].(float64)
	if step2 != 2 {
		t.Fatalf("expected step=2, got %v", step2)
	}
	resp = sendAnswer(t, writer2, reader2, false)
	if resp["status"] != "accepted" {
		t.Fatalf("expected accepted, got %v", resp)
	}
	conn2.Close()

	cmd.Wait()
	if !strings.Contains(stderrBuf.String(), "RESULT:Charlie,false") {
		t.Fatalf("expected RESULT:Charlie,false in stderr, got: %s", stderrBuf.String())
	}
}

func TestSocketCleanupOnExit(t *testing.T) {
	bin := buildSocketTestProgram(t, "text")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}
	cmd.Stdout = &bytes.Buffer{}
	cmd.Stderr = &bytes.Buffer{}

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	if _, err := os.Stat(sockPath); os.IsNotExist(err) {
		t.Fatal("socket file should exist")
	}

	// Answer the prompt so the program exits normally.
	conn, reader, writer := connectSocket(t, sockPath)
	readUntilPrompt(t, reader)
	sendAnswer(t, writer, reader, "done")
	conn.Close()

	cmd.Wait()
	time.Sleep(200 * time.Millisecond)

	if _, err := os.Stat(sockPath); !os.IsNotExist(err) {
		t.Fatal("socket file should be removed after exit")
	}
}

func TestSocketHandshakeOnStdout(t *testing.T) {
	bin := buildSocketTestProgram(t, "text")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}

	stdoutPipe, _ := cmd.StdoutPipe()
	cmd.Stderr = &bytes.Buffer{}

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	hs := readStdoutHandshake(t, stdoutPipe)
	if hs["kind"] != "handshake" {
		t.Fatalf("expected kind=handshake, got %v", hs["kind"])
	}
	if hs["protocol"] != "inquirer-ai" {
		t.Fatalf("expected protocol=inquirer-ai, got %v", hs["protocol"])
	}
	if hs["socket"] != sockPath {
		t.Fatalf("expected socket=%s, got %v", sockPath, hs["socket"])
	}

	// Finish the program.
	conn, reader, writer := connectSocket(t, sockPath)
	readUntilPrompt(t, reader)
	sendAnswer(t, writer, reader, "done")
	conn.Close()

	cmd.Wait()
}

func TestSocketHandshakeOnlyOnFirstConnection(t *testing.T) {
	bin := buildSocketTestProgram(t, "multi")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}
	cmd.Stdout = &bytes.Buffer{}
	cmd.Stderr = &bytes.Buffer{}

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	// First connection: handshake + prompt.
	conn1, reader1, writer1 := connectSocket(t, sockPath)
	msgs1 := readUntilPrompt(t, reader1)
	if len(msgs1) != 2 {
		t.Fatalf("expected 2 messages (handshake + prompt), got %d", len(msgs1))
	}
	if msgs1[0]["kind"] != "handshake" {
		t.Fatalf("expected handshake, got %v", msgs1[0]["kind"])
	}
	if msgs1[1]["kind"] != "prompt" {
		t.Fatalf("expected prompt, got %v", msgs1[1]["kind"])
	}
	sendAnswer(t, writer1, reader1, "test")
	conn1.Close()

	// Second connection: prompt only, no handshake.
	conn2, reader2, writer2 := connectSocket(t, sockPath)
	msgs2 := readUntilPrompt(t, reader2)
	if len(msgs2) != 1 {
		t.Fatalf("expected 1 message (prompt only), got %d", len(msgs2))
	}
	if msgs2[0]["kind"] != "prompt" {
		t.Fatalf("expected prompt, got %v", msgs2[0]["kind"])
	}
	sendAnswer(t, writer2, reader2, true)
	conn2.Close()

	cmd.Wait()
}

func TestSocketSelectPrompt(t *testing.T) {
	bin := buildSocketTestProgram(t, "select")
	sockPath := filepath.Join(t.TempDir(), "test.sock")

	cmd := exec.Command(bin)
	cmd.Env = []string{fmt.Sprintf("INQUIRER_AI_SOCKET=%s", sockPath)}

	var stderrBuf bytes.Buffer
	cmd.Stderr = &stderrBuf
	cmd.Stdout = &bytes.Buffer{}

	if err := cmd.Start(); err != nil {
		t.Fatalf("start: %v", err)
	}
	defer func() {
		cmd.Process.Kill()
		cmd.Wait()
	}()

	waitForSocket(t, sockPath, 5*time.Second)

	conn, reader, writer := connectSocket(t, sockPath)

	msgs := readUntilPrompt(t, reader)
	prompt := msgs[len(msgs)-1]
	if prompt["type"] != "select" {
		t.Fatalf("expected select prompt, got %v", prompt["type"])
	}
	choices, ok := prompt["choices"].([]any)
	if !ok || len(choices) != 3 {
		t.Fatalf("expected 3 choices, got %v", prompt["choices"])
	}

	resp := sendAnswer(t, writer, reader, "Go")
	if resp["status"] != "accepted" {
		t.Fatalf("expected accepted, got %v", resp)
	}
	conn.Close()

	cmd.Wait()
	if !strings.Contains(stderrBuf.String(), "RESULT:Go") {
		t.Fatalf("expected RESULT:Go in stderr, got: %s", stderrBuf.String())
	}
}
