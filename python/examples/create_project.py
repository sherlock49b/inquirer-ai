"""A simple project scaffolding CLI built with inquirer-ai."""

from inquirer_ai import confirm, prompt, select


def main() -> None:
    answers = prompt([
        {
            "type": "input",
            "name": "name",
            "message": "Project name:",
            "default": "my-app",
        },
        {
            "type": "select",
            "name": "language",
            "message": "Language:",
            "choices": [
                {"name": "Python", "value": "python"},
                {"name": "TypeScript", "value": "typescript"},
                {"name": "Go", "value": "go"},
                {"name": "Rust", "value": "rust"},
            ],
        },
        {
            "type": "checkbox",
            "name": "features",
            "message": "Features to include:",
            "choices": [
                {"name": "CI/CD (GitHub Actions)", "value": "ci"},
                {"name": "Docker", "value": "docker"},
                {"name": "Linter", "value": "lint"},
                {"name": "Unit Tests", "value": "test"},
            ],
        },
        {
            "type": "confirm",
            "name": "git_init",
            "message": "Initialize git repository?",
            "default": True,
        },
    ])

    license_type = select(
        "License:",
        choices=["MIT", "Apache-2.0", "GPL-3.0", "None"],
    )
    answers["license"] = license_type

    if answers["features"]:
        setup_now = confirm("Set up selected features now?")
        answers["setup_now"] = setup_now

    print()
    print(f"Creating project: {answers['name']}")
    print(f"  Language: {answers['language']}")
    print(f"  Features: {', '.join(answers['features']) or 'none'}")
    print(f"  Git: {'yes' if answers['git_init'] else 'no'}")
    print(f"  License: {answers['license']}")
    if "setup_now" in answers:
        print(f"  Setup now: {'yes' if answers['setup_now'] else 'no'}")
    print("Done!")


if __name__ == "__main__":
    main()
