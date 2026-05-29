const wrap = require("word-wrap");

const TYPES = {
  feat: { description: "A new feature" },
  fix: { description: "A bug fix" },
  docs: { description: "Documentation only changes" },
  style: { description: "Changes that do not affect the meaning of the code" },
  refactor: { description: "A code change that neither fixes a bug nor adds a feature" },
  perf: { description: "A code change that improves performance" },
  test: { description: "Adding missing tests or correcting existing tests" },
  build: { description: "Changes that affect the build system or external dependencies" },
  ci: { description: "Changes to our CI configuration files and scripts" },
  chore: { description: "Other changes that don't modify src or test files" },
  revert: { description: "Reverts a previous commit" },
};

const MAX_HEADER_WIDTH = 100;
const MAX_LINE_WIDTH = 100;

function headerLength(type, scope) {
  return type.length + 2 + (scope ? scope.length + 2 : 0);
}

function filterSubject(subject) {
  subject = subject.trim();
  if (subject.charAt(0).toUpperCase() === subject.charAt(0)) {
    subject = subject.charAt(0).toLowerCase() + subject.slice(1);
  }
  while (subject.endsWith(".")) {
    subject = subject.slice(0, -1);
  }
  return subject;
}

module.exports = {
  prompter: async function (_cz, commit) {
    try {
      const { text, select, confirm } = await import("inquirer-ai");
      const answers = await promptAll(text, select, confirm);
      const scope = answers.scope ? `(${answers.scope})` : "";
      const head = `${answers.type}${scope}: ${answers.subject}`;
      const wrapOpts = { trim: true, cut: false, newline: "\n", indent: "", width: MAX_LINE_WIDTH };
      const body = answers.body ? wrap(answers.body, wrapOpts) : "";
      const breaking = answers.breaking
        ? wrap(`BREAKING CHANGE: ${answers.breaking.replace(/^BREAKING CHANGE: /, "")}`, wrapOpts)
        : "";
      const issues = answers.issues ? wrap(answers.issues, wrapOpts) : "";
      const parts = [head, body, breaking, issues].filter(Boolean);
      commit(parts.join("\n\n"));
    } catch {
      commit("");
    }
  },
};

async function promptAll(text, select, confirm) {
  const choices = Object.entries(TYPES).map(([key, val]) => ({
    name: `${key.padEnd(10)} ${val.description}`,
    value: key,
    short: key,
  }));

  const type = await select({ message: "Select the type of change that you're committing:", choices });

  const scope = await text({
    message: "What is the scope of this change (e.g. component or file name):",
    filter: (s) => s.trim().toLowerCase(),
  });

  const maxSubject = MAX_HEADER_WIDTH - headerLength(type, scope);

  const subject = await text({
    message: `Write a short, imperative tense description of the change (max ${maxSubject} chars):`,
    validate: (s) => {
      const filtered = filterSubject(s);
      if (!filtered) return "subject is required";
      if (filtered.length > maxSubject)
        return `Subject length must be <= ${maxSubject} characters. Current: ${filtered.length}`;
      return true;
    },
    filter: filterSubject,
  });

  let body = await text({
    message: "Provide a longer description of the change (press enter to skip):",
  });

  const isBreaking = await confirm({ message: "Are there any breaking changes?", default: false });

  let breaking = "";
  if (isBreaking) {
    if (!body) {
      body = await text({
        message: "A BREAKING CHANGE commit requires a body. Please enter a longer description:",
        validate: (s) => (s.trim() ? true : "Body is required for BREAKING CHANGE"),
      });
    }
    breaking = await text({ message: "Describe the breaking changes:" });
  }

  const isIssueAffected = await confirm({
    message: "Does this change affect any open issues?",
    default: false,
  });

  let issues = "";
  if (isIssueAffected) {
    if (!body && !breaking) {
      body = await text({
        message: "The commit requires a body. Please enter a longer description:",
        validate: (s) => (s.trim() ? true : "Body is required"),
      });
    }
    issues = await text({ message: 'Add issue references (e.g. "fix #123", "re #123"):' });
  }

  return { type, scope, subject, body, isBreaking, breaking, isIssueAffected, issues };
}
