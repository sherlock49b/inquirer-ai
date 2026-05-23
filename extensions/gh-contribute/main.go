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

	upstream := detectUpstream()

	body := fmt.Sprintf("## Summary\n- %s\n\n## Test plan\n- %s%s",
		summary, testPlan, breakingNote)

	proceed, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: fmt.Sprintf("Push to origin/%s and create PR to %s?", branch, upstream),
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

	proceed, err := prompt.Confirm(prompt.ConfirmConfig{
		Message: "This will reset your main branch to upstream/main. Continue?",
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
		branch = selected.(string)
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
	runSilent("git", "branch", "-D", branch)
	runSilent("git", "push", "origin", "--delete", branch)
	fmt.Printf("\nBranch '%s' cleaned up.\n", branch)
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

func runSilent(name string, args ...string) {
	exec.Command(name, args...).Run()
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
