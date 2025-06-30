On May 28th, 2024, we introduced automated formatting with `ruff-format` and `pre-commit`. This changed almost every file in the project.
If you forked or branched off before these changes and now try to synchronize your fork/branch with `SWE-agent/SWE-agent:main`, you will
see a lot of merge conflicts.

To solve this, you need to apply the same formatting to your code. Here's how you can do it.

First let's add the official remote (if it exists, you've probably already added it and you can ignore the warning).

```bash
git remote add upstream https://github.com/SWE-agent/SWE-agent.git
git fetch upstream
```

Now, you need the updated `pyproject.toml` and `.pre-commit-config.yaml` files.
We can get them from `SWE-agent/SWE-agent:main`:

```bash
git checkout upstream/main -- .pre-commit-config.yaml pyproject.toml
git commit -m "Update formatting instructions" --no-verify
```

Let's assume that your changes are on branch `FEATURE_BRANCH`, for example, if you've committed to `main`:

```bash
export FEATURE_BRANCH="main"
```

Next we create a copy of this branch (so we don't further modify it):

```bash
git branch "${FEATURE_BRANCH}_REBASED" "${FEATURE_BRANCH}"
```

And now comes the tricky bit: We rebase your changes on top of `upstream/main`, while applying
the formatting fixes at every step:

```bash
git rebase upstream/main "${FEATURE_BRANCH}_REBASED" \
  -Xtheirs \
  --exec 'git reset --soft HEAD^; pre-commit run; pipx run ruff check --fix --unsafe-fixes; git add -u; git commit -C HEAD@{1} --no-verify'
```

!!! note "Understanding the last command"
    Here's what is happening:

    * `git rebase upstream/main "${FEATURE_BRANCH}_REBASED"`
    applies every commit from `"${FEATURE_BRANCH}_REBASED"` on top of `upstream/main`.
    * `-Xtheirs` tells git to always take _your_ changes for merge conflicts
      (rather than the format changes).
    * After every commit, the command from `--exec` is being called.
        * `git reset --soft HEAD^` undos the `git commit` action (while leaving the
          changes staged),
        * then we apply the formatting, and
        * finally we commit the
          formatted changes again.

!!! tip "Still merge conflicts?"
    It's possible that there are non-formatting-related merge conflicts that you are encountering.
    In this case, `git rebase` will stop every time it cannot resolve the conflict.
    Simply fix the merge conflicts as you would normally do (edit the file, commit once done),
    and then run `git rebase --continue`.

You can now open a PR from `${FEATURE_BRANCH}_REBASED` or make it your new default branch.

{% include-markdown "../_footer.md" %}