# Optional git hooks

## `pre-push.sample`

Runs **`scripts/run_autotests.sh`** (line-length check + unit tests) before every push. Install:

```bash
cp scripts/git-hooks/pre-push.sample .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

Removes the “forgot to run tests before push” failure mode; pushes become slower by design.

Not installed by default — opt-in per clone. Agents see the same expectations in **`.cursor/rules/pre-push-quality-gate.mdc`** and **`AGENTS.md`** (fast-path step 6).
