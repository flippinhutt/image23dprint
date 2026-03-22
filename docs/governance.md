# Repository Governance & Review Guide 🛡️

To keep the **Image23DPrint** codebase clean and prevent "messes," follow these GitHub best practices once you push your code:

## 1. Enable Branch Protection (CRITICAL)
Once your repo is on GitHub, go to **Settings > Branches > Add branch protection rule**.
- **Branch name pattern**: `main`
- **Require a pull request before merging**: This prevents anyone (including you, accidentally) from pushing broken code directly to the production branch.
- **Require status checks to pass before merging**: Select your `CI / Code Quality & Dependency Audit` job. This ensures a PR **cannot** be merged if the linter or security scan fails.

## 2. Use the Pull Request Workflow
Never work directly on `main`. Follow this cycle:
1. Create a "feature branch" (e.g., `git checkout -b feature/new-ai-model`).
2. Commit your changes there.
3. Push the branch to GitHub.
4. Open a **Pull Request**.
5. Review the "Files Changed" tab on GitHub. This is your final "sanity check" before the code becomes permanent.

## 3. Implement CODEOWNERS
Create a file at `.github/CODEOWNERS` to automatically assign yourself as a reviewer for any incoming changes.
```text
# Automatically assign @flippinhutt to every PR
* @flippinhutt
```

## 4. GitHub Actions as a "Gatekeeper"
Because we already set up `ci.yml`, GitHub will now show a green checkmark ✅ or a red X ❌ on every PR. **Never merge a red X.** This is your primary defense against a "mess."

---

## 5. Pull Request Template
A standard template is located at `.github/PULL_REQUEST_TEMPLATE.md`. Use this to document your changes, testing methodology, and ensure all checklist items are met before submission.

---

## 🚀 Final Pre-Push Checklist
- [x] `.gitignore` is present (prevents pushing `.venv` or temporary STL files).
- [x] `README.md` and `docs/` are up to date.
- [x] `pyproject.toml` contains all necessary dependencies.
- [x] The code runs locally without errors.
