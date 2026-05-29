package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/sherlock49b/inquirer-ai/go/prompt"
)

func main() {
	if !isGitRepo() {
		fatal("Not a git repository. Run this from inside a git project.")
	}

	action, err := prompt.Select(prompt.SelectConfig{
		Message: "What would you like to do?",
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "Start a new contribution", Value: "new", Description: "Fork + branch from upstream/main"},
			prompt.Choice{Name: "Create a PR from current branch", Value: "pr", Description: "Push and open a pull request"},
			prompt.Choice{Name: "Sync fork with upstream", Value: "sync", Description: "Reset main to upstream/main"},
			prompt.Choice{Name: "Clean up after merge", Value: "cleanup", Description: "Delete branch locally and remotely"},
		},
	})
	if err != nil {
		fatal(err.Error())
	}

	switch action {
	case "new":
		doNewContribution()
	case "pr":
		doCreatePR()
	case "sync":
		doSyncFork()
	case "cleanup":
		doCleanup()
	}
}

func doNewContribution() {
	if !hasRemote("upstream") {
		upstream, err := prompt.Text(prompt.TextConfig{
			Message: "Upstream repo URL (e.g., https://github.com/org/repo.git)",
			Validate: func(s string) error {
				if !strings.Contains(s, "github.com") {
					return fmt.Errorf("must be a GitHub URL")
				}
				return nil
			},
		})
		if err != nil {
			fatal(err.Error())
		}
		run("git", "remote", "add", "upstream", upstream)
		fmt.Println("Added upstream remote.")
	}

	run("git", "fetch", "upstream")

	branchType, err := prompt.Select(prompt.SelectConfig{
		Message: "Branch type",
		Choices: []prompt.ChoiceItem{
			prompt.Choice{Name: "feat — new feature", Value: "feat"},
			prompt.Choice{Name: "fix — bug fix", Value: "fix"},
			prompt.Choice{Name: "test — adding tests", Value: "test"},
			prompt.Choice{Name: "refactor — restructuring", Value: "refactor"},
			prompt.Choice{Name: "docs — documentation", Value: "docs"},
			prompt.Choice{Name: "chore — maintenance", Value: "chore"},
		},
	})
	if err != nil {
		fatal(err.Error())
	}

	description, err := prompt.Text(prompt.TextConfig{
		Message: "Short description (kebab-case, e.g., add-oauth-support)",
		Validate: func(s string) error {
			if strings.TrimSpace(s) == "" {
				return fmt.Errorf("description is required")
			}
			return nil
		},
		Filter: func(s string) string {
			return strings.TrimSpace(strings.ReplaceAll(s, " ", "-"))
		},
	})
	if err != nil {
		fatal(err.Error())
	}

	branch := fmt.Sprintf("%s/%s", branchType, description)
	run("git", "checkout", "-b", branch, "upstream/main")
	fmt.Printf("\nBranch '%s' created from upstream/main.\n", branch)
	fmt.Println("Make your changes, then run: gh contribute → Create a PR")
}

func doCreatePR() {
	branch := currentBranch()
	if branch == "main" || branch == "master" {
		fatal("You are on the default branch. Switch to a feature branch first.")
	}

	parts := strings.SplitN(branch, "/", 2)
	defaultTitle := branch
	if len(parts) == 2 {
		defaultTitle = fmt.Sprintf("%s: %s", parts[0], strings.ReplaceAll(parts[1], "-", " "))
	}

	title, err := prompt.Text(prompt.TextConfig{
		Message: "PR title",
		Default: defaultTitle,
	})
	if err != nil {
		fatal(err.Error())
	}

	summary, err := prompt.Text(prompt.TextConfig{
		Message: "What does this PR do? (one-line summary)",
	})
	if err != nil {
		fatal(err.Error())
	}

	testPlan, err := prompt.Text(prompt.TextConfig{
		Message: "How was this tested?",
		Default: "Tests pass locally",
	})
	if err != nil {
		fatal(err.Error())
	}

	hasBreaking, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: "Does this include breaking changes?",
	})
	if err != nil {
		fatal(err.Error())
	}

	breakingNote := ""
	if hasBreaking {
		note, err := prompt.Text(prompt.TextConfig{
			Message: "Describe the breaking change",
		})
		if err != nil {
			fatal(err.Error())
		}
		breakingNote = fmt.Sprintf("\n\n## Breaking Changes\n- %s", note)
	}

	// Determine the PR target. If an upstream remote exists but we cannot
	// resolve it to an "owner/repo" slug (e.g. a non-GitHub host, an SSH/
	// enterprise URL we do not recognise), abort rather than silently opening
	// the PR against the fork (origin).
	upstream := ""
	if hasRemote("upstream") {
		upstream = detectUpstream()
		if upstream == "" {
			rawURL, _ := exec.Command("git", "remote", "get-url", "upstream").Output()
			fatal(fmt.Sprintf(
				"Could not derive an 'owner/repo' from the upstream remote (%s).\n"+
					"Only github.com HTTPS/SSH URLs are supported. Set the PR target manually with:\n"+
					"  gh pr create --repo <owner>/<repo>",
				strings.TrimSpace(string(rawURL))))
		}
	}

	body := fmt.Sprintf("## Summary\n- %s\n\n## Test plan\n- %s%s",
		summary, testPlan, breakingNote)

	target := upstream
	if target == "" {
		target = "origin (no upstream remote configured)"
	}
	proceed, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: fmt.Sprintf("Push to origin/%s and create PR to %s?", branch, target),
		Default: true,
	})
	if err != nil {
		fatal(err.Error())
	}
	if !proceed {
		fmt.Println("Aborted.")
		return
	}

	run("git", "push", "-u", "origin", branch)

	args := []string{"pr", "create", "--title", title, "--body", body}
	if upstream != "" {
		args = append(args, "--repo", upstream)
	}
	runGH(args...)

	fmt.Println("\nPR created successfully.")
}

func doSyncFork() {
	if !hasRemote("upstream") {
		fatal("No upstream remote configured. Run 'Start a new contribution' first.")
	}

	// Refuse to force-push if origin and upstream point at the same repo —
	// otherwise we would be force-pushing main onto the upstream itself.
	originURL := remoteURL("origin")
	upstreamURL := remoteURL("upstream")
	if originURL != "" && sameRepo(originURL, upstreamURL) {
		fatal(fmt.Sprintf(
			"origin and upstream point at the same repository (%s).\n"+
				"Refusing to force-push main onto the upstream. Configure a separate fork as 'origin' first.",
			originURL))
	}

	proceed, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: "This will reset main to upstream/main and FORCE-PUSH it to origin (overwriting origin/main). Continue?",
		Default: true,
	})
	if err != nil {
		fatal(err.Error())
	}
	if !proceed {
		return
	}

	run("git", "fetch", "upstream")
	run("git", "checkout", "main")
	run("git", "reset", "--hard", "upstream/main")
	run("git", "push", "origin", "main", "--force")
	fmt.Println("\nFork synced with upstream.")
}

func doCleanup() {
	branch := currentBranch()
	if branch == "main" || branch == "master" {
		branches := listBranches()
		if len(branches) == 0 {
			fmt.Println("No feature branches to clean up.")
			return
		}

		selected, err := prompt.Select(prompt.SelectConfig{
			Message: "Which branch to clean up?",
			Choices: toChoiceItems(branches),
		})
		if err != nil {
			fatal(err.Error())
		}
		s, ok := selected.(string)
		if !ok {
			fatal(fmt.Sprintf("Unexpected selection type %T (expected a branch name string)", selected))
		}
		branch = s
	}

	deleteRemote, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: fmt.Sprintf("Delete branch '%s' locally and from origin?", branch),
		Default: true,
	})
	if err != nil {
		fatal(err.Error())
	}
	if !deleteRemote {
		return
	}

	run("git", "checkout", "main")

	// Use the merge-safe `git branch -d` first. If the branch is not fully
	// merged, git refuses; offer an explicit force (`-D`) rather than silently
	// destroying unmerged work.
	if err := tryRun("git", "branch", "-d", branch); err != nil {
		fmt.Printf("Local branch '%s' is not fully merged: %v\n", branch, err)
		force, ferr := prompt.Confirm(prompt.ConfirmConfig{
			Message: fmt.Sprintf("Force-delete unmerged local branch '%s'? (git branch -D)", branch),
			Default: false,
		})
		if ferr != nil {
			fatal(ferr.Error())
		}
		if force {
			if err := tryRun("git", "branch", "-D", branch); err != nil {
				fmt.Printf("Failed to force-delete local branch '%s': %v\n", branch, err)
			} else {
				fmt.Printf("Force-deleted local branch '%s'.\n", branch)
			}
		} else {
			fmt.Printf("Kept local branch '%s'.\n", branch)
		}
	} else {
		fmt.Printf("Deleted local branch '%s'.\n", branch)
	}

	if err := tryRun("git", "push", "origin", "--delete", branch); err != nil {
		fmt.Printf("Could not delete remote branch 'origin/%s': %v\n", branch, err)
	} else {
		fmt.Printf("Deleted remote branch 'origin/%s'.\n", branch)
	}

	fmt.Printf("\nCleanup of '%s' complete.\n", branch)
}

// --- helpers ---

func isGitRepo() bool {
	return exec.Command("git", "rev-parse", "--is-inside-work-tree").Run() == nil
}

func hasRemote(name string) bool {
	out, _ := exec.Command("git", "remote").Output()
	for _, line := range strings.Split(string(out), "\n") {
		if strings.TrimSpace(line) == name {
			return true
		}
	}
	return false
}

func currentBranch() string {
	out, _ := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD").Output()
	return strings.TrimSpace(string(out))
}

func detectUpstream() string {
	out, _ := exec.Command("git", "remote", "get-url", "upstream").Output()
	url := strings.TrimSpace(string(out))
	url = strings.TrimSuffix(url, ".git")
	if strings.HasPrefix(url, "https://github.com/") {
		return strings.TrimPrefix(url, "https://github.com/")
	}
	if strings.HasPrefix(url, "git@github.com:") {
		return strings.TrimPrefix(url, "git@github.com:")
	}
	return ""
}

// remoteURL returns the configured URL for a remote, or "" if it has none.
func remoteURL(name string) string {
	out, _ := exec.Command("git", "remote", "get-url", name).Output()
	return strings.TrimSpace(string(out))
}

// normalizeRepoURL reduces a git remote URL to a comparable "host/owner/repo"
// form so two URLs for the same repository (https vs ssh, trailing .git, etc.)
// compare equal.
func normalizeRepoURL(url string) string {
	u := strings.TrimSpace(url)
	u = strings.TrimSuffix(u, "/")
	u = strings.TrimSuffix(u, ".git")
	u = strings.TrimPrefix(u, "https://")
	u = strings.TrimPrefix(u, "http://")
	u = strings.TrimPrefix(u, "ssh://")
	u = strings.TrimPrefix(u, "git@")
	// scp-style "git@host:owner/repo" -> "host/owner/repo"
	u = strings.Replace(u, ":", "/", 1)
	return strings.ToLower(u)
}

func sameRepo(a, b string) bool {
	if a == "" || b == "" {
		return false
	}
	return normalizeRepoURL(a) == normalizeRepoURL(b)
}

func listBranches() []string {
	out, _ := exec.Command("git", "branch", "--format=%(refname:short)").Output()
	var branches []string
	for _, b := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		b = strings.TrimSpace(b)
		if b != "" && b != "main" && b != "master" {
			branches = append(branches, b)
		}
	}
	return branches
}

func toChoiceItems(items []string) []prompt.ChoiceItem {
	choices := make([]prompt.ChoiceItem, len(items))
	for i, item := range items {
		choices[i] = prompt.Choice{Name: item, Value: item}
	}
	return choices
}

func run(name string, args ...string) {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		fatal(fmt.Sprintf("command failed: %s %s: %v", name, strings.Join(args, " "), err))
	}
}

// tryRun runs a command, forwarding output to stderr, and returns its error
// (instead of aborting the whole program) so callers can report per-step
// outcomes and continue.
func tryRun(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func runGH(args ...string) {
	cmd := exec.Command("gh", args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if err := cmd.Run(); err != nil {
		fatal(fmt.Sprintf("gh command failed: %v", err))
	}
}

func fatal(msg string) {
	fmt.Fprintf(os.Stderr, "Error: %s\n", msg)
	os.Exit(1)
}
