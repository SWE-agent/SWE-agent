# Contribution guidelines

<!-- Please don't use relative links in this page, as it is included by github in various places -->
<!-- INCLUSION START -->

The easiest way to contribute is to give us feedback.

* **Something isn't working?** Open a [bug report](https://github.com/SWE-agent/SWE-agent/issues/new?template=bug_report.yml).
  Rule of thumb: If you're running something and you get some error messages, this is the issue type for you.
* **You have a concrete question?** Open a [question issue](https://github.com/SWE-agent/SWE-agent/issues/new?template=question.yml).
* **You are missing something?** Open a [feature request issue](https://github.com/SWE-agent/SWE-agent/issues/new?template=feature_request.yml)
* **Open-ended discussion?** Talk on [discord](https://discord.gg/AVEFbBn2rH). Note that all actionable items should be an issue though.

<!-- INCLUSION END -->

You want to do contribute to the development? Great! Please see the [development guidelines](https://swe-agent.com/latest/dev/contribute/) for guidelines and tips.

## Line Endings
To ensure consistent behavior across different platforms and prevent patch application issues:

- All text files use LF (Unix-style) line endings
- This is enforced via `.gitattributes` for all contributors
- Windows users: Configure Git to handle line endings correctly:
  ```bash
  git config --global core.autocrlf input
  ```
- If you experience patch failures, check your line endings with `git ls-files --eol`
