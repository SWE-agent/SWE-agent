# Changelog

## SWE-agent 1.1.0 (2025-05-22)

We're very excited to announce our new project [SWE-smith](https://swesmith.com/), generating 10s of thousands of training trajectories for SWE agents.
Using this training data, our LM SWE-agent-LM-32b achieves open-weights SotA on SWE-bench verified with SWE-agent!

Apart from that, v1.1.0 is mostly a fix release with minor improvements, in particular adding compatibility with SWE-bench multilingual/multimodal, and SWE-smith.

### Breaking changes

* Changes to trajectory data format. The `messages` field is replaced by `query` by [@klieret](https://github.com/klieret) in [#1107](https://github.com/princeton-nlp/SWE-agent/pull/1107)
* Renamed many tool bundles that used "windowed" file viewer (`defaults` and more) by [@klieret](https://github.com/klieret) in [#1147](https://github.com/princeton-nlp/SWE-agent/pull/1147)
* Removed `review_on_submit` tool bundle (replaced by `review_on_submit_m`) by [@klieret](https://github.com/klieret) in [#1148](https://github.com/princeton-nlp/SWE-agent/pull/1148)
* Change in `windowed` tools (formerly `default`): Don't append \n to new file by [@klieret](https://github.com/klieret) in [#1114](https://github.com/princeton-nlp/SWE-agent/pull/1114)

### Added

New dataset support:

* Feat: Support multilingual evaluation by [@kabirgh](https://github.com/kabirgh) in [#1090](https://github.com/princeton-nlp/SWE-agent/pull/1090)
* Feat: SWE-smith & multimodal base support by [@klieret](https://github.com/klieret) in [#1092](https://github.com/princeton-nlp/SWE-agent/pull/1092)

New utilities:

* Feat: Add quick-stats tool by [@klieret](https://github.com/klieret) in [#1125](https://github.com/princeton-nlp/SWE-agent/pull/1125)

### Enhanced

* Feat: Config/override max_output_tokens by [@klieret](https://github.com/klieret) in [#1036](https://github.com/princeton-nlp/SWE-agent/pull/1036)
* Enh: [#1042] fix(run_batch): handle JSON parsing errors in trajectory check by [@FRAOTIAC](https://github.com/FRAOTIAC) in [#1043](https://github.com/princeton-nlp/SWE-agent/pull/1043)
* Enh: Allow to override tools dirs etc. by [@klieret](https://github.com/klieret) in [#1046](https://github.com/princeton-nlp/SWE-agent/pull/1046)
* Enh: Allow to override path to swe-bench dataset by [@klieret](https://github.com/klieret) in [#1093](https://github.com/princeton-nlp/SWE-agent/pull/1093)
* Enh: Allow to disable python-standalone for batch by [@klieret](https://github.com/klieret) in [#1115](https://github.com/princeton-nlp/SWE-agent/pull/1115)
* Enh: More information on skipped exit status by [@klieret](https://github.com/klieret) in [#1117](https://github.com/princeton-nlp/SWE-agent/pull/1117)

### Fixed

* Fix: Setting max_input_tokens to 0 by [@klieret](https://github.com/klieret) in [#999](https://github.com/princeton-nlp/SWE-agent/pull/999)
* Fix: Explicitly set log file encoding by [@klieret](https://github.com/klieret) in [#1013](https://github.com/princeton-nlp/SWE-agent/pull/1013)
* Fix: Ensure pydantic-settings env prefix set by [@klieret](https://github.com/klieret) in [#1018](https://github.com/princeton-nlp/SWE-agent/pull/1018)
* Fix: run batch processing with modal by [@vsee](https://github.com/vsee) in [#1023](https://github.com/princeton-nlp/SWE-agent/pull/1023)
* Fix: Catch exit forfeit by [@klieret](https://github.com/klieret) in [#1024](https://github.com/princeton-nlp/SWE-agent/pull/1024)
* Fix: Use 'latest' image tag for SWE-Bench images by [@klieret](https://github.com/klieret) in [#1029](https://github.com/princeton-nlp/SWE-agent/pull/1029)
* Fix: Show tenacity retry reasons by [@klieret](https://github.com/klieret) in [#1032](https://github.com/princeton-nlp/SWE-agent/pull/1032)
* Fix: Compatibility with textual 2.0 by [@klieret](https://github.com/klieret) in [#1033](https://github.com/princeton-nlp/SWE-agent/pull/1033)
* Fix: Use default trajectories dir according to ENV by [@vsee](https://github.com/vsee) in [#1054](https://github.com/princeton-nlp/SWE-agent/pull/1054)
* Fix: fix Windows path error, replace Path with PurePosixPath or string by [@alwaysgoodtime](https://github.com/alwaysgoodtime) in [#1052](https://github.com/princeton-nlp/SWE-agent/pull/1052)
* Fix: Ensure tools PATH takes precedence by [@klieret](https://github.com/klieret) in [#1058](https://github.com/princeton-nlp/SWE-agent/pull/1058)
* Fix: Ensure state exists by [@klieret](https://github.com/klieret) in [#1065](https://github.com/princeton-nlp/SWE-agent/pull/1065)
* Fix spelling of 'agent' in hello world by [@edspencer](https://github.com/edspencer) in [#1077](https://github.com/princeton-nlp/SWE-agent/pull/1077)
* Fix: Inspector needs to handle new message format by [@klieret](https://github.com/klieret) in [#1094](https://github.com/princeton-nlp/SWE-agent/pull/1094)
* Fix: SWEBenchInstances with path and no subset initiated as other instance type by [@klieret](https://github.com/klieret) in [#1096](https://github.com/princeton-nlp/SWE-agent/pull/1096)
* Fix: Token limit exceeded for PR body issue by [@klieret](https://github.com/klieret) in [#1098](https://github.com/princeton-nlp/SWE-agent/pull/1098)
* Fix: Work around litellm claude 3.7 tokens to 128k by [@klieret](https://github.com/klieret) in [#1106](https://github.com/princeton-nlp/SWE-agent/pull/1106)
* Fix(repo): Ensure absolute path for copy repo by [@klieret](https://github.com/klieret) in [#1116](https://github.com/princeton-nlp/SWE-agent/pull/1116)
* Fix execution time timeouts by [@klieret](https://github.com/klieret) in [#1118](https://github.com/princeton-nlp/SWE-agent/pull/1118)
* Fix: Hierarchical merge of multiple configs by [@klieret](https://github.com/klieret) in [#1123](https://github.com/princeton-nlp/SWE-agent/pull/1123)
* fix message type missing by [@klieret](https://github.com/klieret) in [#1127](https://github.com/princeton-nlp/SWE-agent/pull/1127)
* Fix: Conditional for warning about empty template by [@klieret](https://github.com/klieret) in [#1137](https://github.com/princeton-nlp/SWE-agent/pull/1137)

### New Contributors

* [@vsee](https://github.com/vsee) made their first contribution in [#1023](https://github.com/princeton-nlp/SWE-agent/pull/1023)
* [@FRAOTIAC](https://github.com/FRAOTIAC) made their first contribution in [#1043](https://github.com/princeton-nlp/SWE-agent/pull/1043)
* [@jpaodev](https://github.com/jpaodev) made their first contribution in [#1050](https://github.com/princeton-nlp/SWE-agent/pull/1050)
* [@alwaysgoodtime](https://github.com/alwaysgoodtime) made their first contribution in [#1052](https://github.com/princeton-nlp/SWE-agent/pull/1052)
* [@alexgshaw](https://github.com/alexgshaw) made their first contribution in [#1056](https://github.com/princeton-nlp/SWE-agent/pull/1056)
* [@talorabr](https://github.com/talorabr) made their first contribution in [#1026](https://github.com/princeton-nlp/SWE-agent/pull/1026)
* [@katia](https://github.com/katia)-sentry made their first contribution in [#1070](https://github.com/princeton-nlp/SWE-agent/pull/1070)
* [@edspencer](https://github.com/edspencer) made their first contribution in [#1077](https://github.com/princeton-nlp/SWE-agent/pull/1077)
* [@kabirgh](https://github.com/kabirgh) made their first contribution in [#1090](https://github.com/princeton-nlp/SWE-agent/pull/1090)

**Full Changelog**: https://github.com/SWE-agent/SWE-agent/compare/v1.0.1...v1.1.0

## SWE-agent 1.0.1 (2025-02-28)

This fixup release brings fixes mostly to the compatibility with local models. We have also significantly expanded the documentation in that aspect ([models & keys documentation](https://swe-agent.com/latest/installation/keys/)).

### Changed

* Change: Make anthropic_filemap the new default config by [@klieret](https://github.com/klieret) in [#927](https://github.com/princeton-nlp/SWE-agent/pull/927)

### Added

* Enh: Set timeout for post_startup_commands by [@klieret](https://github.com/klieret) in [#973](https://github.com/princeton-nlp/SWE-agent/pull/973)
* Enh: Allow to override max_input_tokens for local models by [@klieret](https://github.com/klieret) in [#992](https://github.com/princeton-nlp/SWE-agent/pull/992)

### Fixes

* Fix: Handling local models cost lookup issues by [@klieret](https://github.com/klieret) in [#937](https://github.com/princeton-nlp/SWE-agent/pull/937)
* Fix: Requires-python >= 3.11 by [@klieret](https://github.com/klieret) in [#940](https://github.com/princeton-nlp/SWE-agent/pull/940)
* traj inspector viewport reset by [@klieret](https://github.com/klieret) in [#946](https://github.com/princeton-nlp/SWE-agent/pull/946)
* Fix: Reset viewport when next/prev step/traj by [@klieret](https://github.com/klieret) in [#948](https://github.com/princeton-nlp/SWE-agent/pull/948)
* Fix: Disable highlighting of model outputs by [@klieret](https://github.com/klieret) in [#949](https://github.com/princeton-nlp/SWE-agent/pull/949)
* Fix: Create PRs by [@klieret](https://github.com/klieret) in [#954](https://github.com/princeton-nlp/SWE-agent/pull/954)
* Fix: Add __init__,py to agent/hooks by [@RNabel](https://github.com/RNabel) in [#961](https://github.com/princeton-nlp/SWE-agent/pull/961)
* Fix: Pin textual to version 1.0.0 by [@RNabel](https://github.com/RNabel) in [#960](https://github.com/princeton-nlp/SWE-agent/pull/960)
* Fix: OpenAI API: Don't pass None tool_calls to the OpenAI API by [@RNabel](https://github.com/RNabel) in [#967](https://github.com/princeton-nlp/SWE-agent/pull/967)
* Fix: Forces platform to be linux/amd64 for swe-bench batch runs by [@carlosejimenez](https://github.com/carlosejimenez) in [#942](https://github.com/princeton-nlp/SWE-agent/pull/942)
* Fix "TypeError: Cannot read properties of null (reading 'replace')" in Trajectory viewer by [@0xba1a](https://github.com/0xba1a) in [#989](https://github.com/princeton-nlp/SWE-agent/pull/989)
* Fix: No retries if costs cannot be calculated by [@klieret](https://github.com/klieret) in [#990](https://github.com/princeton-nlp/SWE-agent/pull/990)
* Fix: Race condition/size change during iteration by [@klieret](https://github.com/klieret) in [#993](https://github.com/princeton-nlp/SWE-agent/pull/993)
* Fix: Handle total cost limit exceeded by [@klieret](https://github.com/klieret) in [#994](https://github.com/princeton-nlp/SWE-agent/pull/994)

## New Contributors

* [@RNabel](https://github.com/RNabel) made their first contribution in [#961](https://github.com/princeton-nlp/SWE-agent/pull/961)
* [@dhruvji](https://github.com/dhruvji) made their first contribution in [#963](https://github.com/princeton-nlp/SWE-agent/pull/963)
* [@0xba1a](https://github.com/0xba1a) made their first contribution in [#989](https://github.com/princeton-nlp/SWE-agent/pull/989)

**Full Changelog**: https://github.com/SWE-agent/SWE-agent/compare/v1.0.0...v1.0.1

## 1.0.0 (2025-02-13)

This is a massive release that includes many new features, fixes, and changes.
You can read more about the changes in the [migration guide](migration.md).

### Added

* Fast, massively parallel code execution with [SWE-ReX](https://github.com/swe-agent/SWE-ReX).
* Run SWE-agent locally but execute code in the cloud (using modal, AWS, or anything else that runs [SWE-ReX](https://github.com/swe-agent/SWE-ReX)).
* Configurable retry mechanisms: Try multiple agent configurations, models, parameters, etc., then choose the best one.
* Flexible tool definitions with [tool bundles](../config/tools.md).
* All language models supported using `litellm` (see [models](../installation/keys.md)).
* Override any configuration option from the command line (see [command line basics](../usage/cl_tutorial.md)).
* New [command line trajectory inspector](../usage/inspector.md) to scroll few hundreds of trajectories with ease.
* [New command line interface](../usage/cli.md) with subcommands for running over single issues, batches, and various utility commands.
* Greatly simplified and cleaned up codebase. In particular, the `Agent` class is now much easier to modify.

### Changed

* The code base has been largely rewritten. Lots of things have moved and changed.
* The biggest change is that we now use [SWE-ReX](https://github.com/swe-agent/SWE-ReX) for code execution. This allowed us to remove a lot of distracting code from the agent.
* We now use [`pydantic`](https://docs.pydantic.dev/) for all configuration.
* Templates are now [`jinja2`](https://jinja.palletsprojects.com/) templates, which gives you more flexibility (but you'll have to update your templates)
* All models are now configured using `litellm` (see [models](../installation/keys.md)).

See the [migration guide](migration.md) for more details.

### New contributors

* [@manya706](https://github.com/manya706) made their first contribution in [#787](https://github.com/princeton-nlp/SWE-agent/pull/787)
* [@Prathamesh010](https://github.com/Prathamesh010) made their first contribution in [#796](https://github.com/princeton-nlp/SWE-agent/pull/796)
* [@magnimusprime](https://github.com/magnimusprime) made their first contribution in [#813](https://github.com/princeton-nlp/SWE-agent/pull/813)
* [@dependabot](https://github.com/dependabot) made their first contribution in [#817](https://github.com/princeton-nlp/SWE-agent/pull/817)
* [@Mefisto04](https://github.com/Mefisto04) made their first contribution in [#824](https://github.com/princeton-nlp/SWE-agent/pull/824)
* [@acheshkov](https://github.com/acheshkov) made their first contribution in [#857](https://github.com/princeton-nlp/SWE-agent/pull/857)
* [@yu-iskw](https://github.com/yu-iskw) made their first contribution in [#881](https://github.com/princeton-nlp/SWE-agent/pull/881)

## 0.7.0 (2024-09-23)

### Added

The main new feature is the **EnIGMA mode**, which included additions like support for Interactive Agent Tools
and Summarizers.

* Add filemap command in the spirit of repomap by [@samuela](https://github.com/samuela) in [#619](https://github.com/princeton-nlp/SWE-agent/pull/619)
* Create config to run human eval style challenges by [@ofirpress](https://github.com/ofirpress) in [#658](https://github.com/princeton-nlp/SWE-agent/pull/658)
* Add claude 3.5 sonnet to models by [@carlosejimenez](https://github.com/carlosejimenez) in [#601](https://github.com/princeton-nlp/SWE-agent/pull/601)
* Enh: Warn if scrolling >= 3 times by [@klieret](https://github.com/klieret) in [#626](https://github.com/princeton-nlp/SWE-agent/pull/626)
* feat: support deepseek-coder LLM by [@jcraftsman](https://github.com/jcraftsman) in [#638](https://github.com/princeton-nlp/SWE-agent/pull/638)
* Enh: Make timeout for agent commands configurable by [@klieret](https://github.com/klieret) in [#674](https://github.com/princeton-nlp/SWE-agent/pull/674)
* Add support for new gpt-4o-mini model by [@ivan4722](https://github.com/ivan4722) in [#693](https://github.com/princeton-nlp/SWE-agent/pull/693)
* Groq Models Integration by [@MohammedNagdy](https://github.com/MohammedNagdy) in [#721](https://github.com/princeton-nlp/SWE-agent/pull/721)
* Make log level configurable; add TRACE level by [@klieret](https://github.com/klieret) in [#612](https://github.com/princeton-nlp/SWE-agent/pull/612)

### Fixes

* Compatibility with SWE-bench 2.0 by [@klieret](https://github.com/klieret) in [#671](https://github.com/princeton-nlp/SWE-agent/pull/671)
* ensure variables work in special command docstring by [@forresty](https://github.com/forresty) in [#628](https://github.com/princeton-nlp/SWE-agent/pull/628)
* Important fix: Catch CostLimitExceeded in retry because of format/block by [@klieret](https://github.com/klieret) in [#682](https://github.com/princeton-nlp/SWE-agent/pull/682)
* Fix: Handle empty traj in should_skip by [@klieret](https://github.com/klieret) in [#616](https://github.com/princeton-nlp/SWE-agent/pull/616)
* Fix for end-marker communicate: Exit status always 0/invalid by [@klieret](https://github.com/klieret) in [#644](https://github.com/princeton-nlp/SWE-agent/pull/644)
* Fix: Insufficient quoting of git commit message by [@klieret](https://github.com/klieret) in [#646](https://github.com/princeton-nlp/SWE-agent/pull/646)
* Fix nonsensical trajectory formatting for PRs by [@klieret](https://github.com/klieret) in [#647](https://github.com/princeton-nlp/SWE-agent/pull/647)
* Fix: sweunexpected keyword 'python_version' by [@klieret](https://github.com/klieret) in [#692](https://github.com/princeton-nlp/SWE-agent/pull/692)
* Fix: Use LONG_TIMEOUT for pre_install commands by [@klieret](https://github.com/klieret) in [#695](https://github.com/princeton-nlp/SWE-agent/pull/695)
* Fix: UnboundLocalError when catching decoding issue by [@klieret](https://github.com/klieret) in [#709](https://github.com/princeton-nlp/SWE-agent/pull/709)
* Also create empty patch files for completeness by [@klieret](https://github.com/klieret) in [#725](https://github.com/princeton-nlp/SWE-agent/pull/725)
* Fix: Raise ContextWindowExceeded instead of exit_cost by [@klieret](https://github.com/klieret) in [#727](https://github.com/princeton-nlp/SWE-agent/pull/727)
* Fix: Deal with non-utf8 encoded bytes in comm by [@klieret](https://github.com/klieret) in [#731](https://github.com/princeton-nlp/SWE-agent/pull/731)
* Fix: Handle spaces in repo names by [@klieret](https://github.com/klieret) in [#734](https://github.com/princeton-nlp/SWE-agent/pull/734)
* Fix: Ensure utils is part of package by [@klieret](https://github.com/klieret) in [#742](https://github.com/princeton-nlp/SWE-agent/pull/742)
* Fix: Submitting ' ' in human mode crashes container by [@klieret](https://github.com/klieret) in [#749](https://github.com/princeton-nlp/SWE-agent/pull/749)
* Fix: Block su as command by [@klieret](https://github.com/klieret) in [#752](https://github.com/princeton-nlp/SWE-agent/pull/752)
* Fix: SWE_AGENT_MODEL_MAX_RETRIES needs casting by [@klieret](https://github.com/klieret) in [#757](https://github.com/princeton-nlp/SWE-agent/pull/757)

### New Contributors

🎉 **[@talorabr](https://github.com/talorabr), [@udiboy1209](https://github.com/udiboy1209), [@haoranxi](https://github.com/haoranxi), [@NickNameInvalid](https://github.com/NickNameInvalid), [@rollingcoconut](https://github.com/rollingcoconut) joined the team to build EnIGMA** 🎉

* [@samefarrar](https://github.com/samefarrar) made their first contribution in [#606](https://github.com/princeton-nlp/SWE-agent/pull/606)
* [@hubstrauss](https://github.com/hubstrauss) made their first contribution in [#625](https://github.com/princeton-nlp/SWE-agent/pull/625)
* [@samuela](https://github.com/samuela) made their first contribution in [#619](https://github.com/princeton-nlp/SWE-agent/pull/619)
* [@forresty](https://github.com/forresty) made their first contribution in [#628](https://github.com/princeton-nlp/SWE-agent/pull/628)
* [@jcraftsman](https://github.com/jcraftsman) made their first contribution in [#638](https://github.com/princeton-nlp/SWE-agent/pull/638)
* [@ivan4722](https://github.com/ivan4722) made their first contribution in [#693](https://github.com/princeton-nlp/SWE-agent/pull/693)
* [@JoshuaPurtell](https://github.com/JoshuaPurtell) made their first contribution in [#703](https://github.com/princeton-nlp/SWE-agent/pull/703)
* [@MohammedNagdy](https://github.com/MohammedNagdy) made their first contribution in [#721](https://github.com/princeton-nlp/SWE-agent/pull/721)
* [@pdemro](https://github.com/pdemro) made their first contribution in [#729](https://github.com/princeton-nlp/SWE-agent/pull/729)

## 0.6.1 (2024-06-20)

[All new commits](https://github.com/SWE-agent/SWE-agent/compare/v0.6.0...v0.6.1)

This is (mostly) a patch release, in particular fixing several issues that had been introduced by the speed improvements of v0.6.0.
We also solve a bug where existing linter errors in a file left SWE-agent unable to edit (because of our lint-retry-loop).

### Breaking changes

* Change: sparse clone method is now correctly called "shallow" by [@klieret](https://github.com/klieret) in [#591](https://github.com/princeton-nlp/SWE-agent/pull/591)

### Improved

* Enh: Show commands when encountering timeout error by [@klieret](https://github.com/klieret) in [#582](https://github.com/princeton-nlp/SWE-agent/pull/582)
* Enh: Configuration option to show time in log by [@klieret](https://github.com/klieret) in [#583](https://github.com/princeton-nlp/SWE-agent/pull/583)
* Enh: Allow to configure LONG_TIMEOUT for SWEEnv by [@klieret](https://github.com/klieret) in [#584](https://github.com/princeton-nlp/SWE-agent/pull/584)
* Enh: Always write log to traj directory by [@klieret](https://github.com/klieret) in [#588](https://github.com/princeton-nlp/SWE-agent/pull/588)

### Fixed

* fix `docker.errors.NotFound` by [@klieret](https://github.com/klieret) in [#587](https://github.com/princeton-nlp/SWE-agent/pull/587)
* Fix: Revert to full clone method when needed by [@klieret](https://github.com/klieret) in [#589](https://github.com/princeton-nlp/SWE-agent/pull/589)
* Fix: Refresh container_obj before querying status by [@klieret](https://github.com/klieret) in [#590](https://github.com/princeton-nlp/SWE-agent/pull/590)
* Fixed #571 - show message that model arg is ignored in case of using Azure OpenAI by [@jank](https://github.com/jank) in [#592](https://github.com/princeton-nlp/SWE-agent/pull/592)
* Fix: Linting blocks for existing lint errors by [@klieret](https://github.com/klieret) in [#593](https://github.com/princeton-nlp/SWE-agent/pull/593)
* Fix: Process done marker not found in read with timeout by [@klieret](https://github.com/klieret) in [#596](https://github.com/princeton-nlp/SWE-agent/pull/596)

## 0.6.0 (2024-06-05)

[All new commits](https://github.com/SWE-agent/SWE-agent/compare/v0.5.0...v0.6.0)

**We sped up SWE-agent by 2x** (timed with GPT4o). This is mostly due to faster communication with the running processes inside of the Docker container and other container setup & installation related improvements. Here are a few relevant PRs:

* Switch to fast communicate and shallow clone by default by [@klieret](https://github.com/klieret) in [#530](https://github.com/princeton-nlp/SWE-agent/pull/530)
* Change: Only wait 1s for docker to start by [@klieret](https://github.com/klieret) in [#541](https://github.com/princeton-nlp/SWE-agent/pull/541)
* Feat: experimental shallow cloning by [@klieret](https://github.com/klieret) in [#498](https://github.com/princeton-nlp/SWE-agent/pull/498)
* Enh: Start from clone of python conda environment for speedup by [@klieret](https://github.com/klieret) in [#548](https://github.com/princeton-nlp/SWE-agent/pull/548)
* Enh: Use uv for editable install by default by [@klieret](https://github.com/klieret) in [#547](https://github.com/princeton-nlp/SWE-agent/pull/547)

### Improved

* Improve scrolling behavior in web UI by [@anishfish2](https://github.com/anishfish2) in [#420](https://github.com/princeton-nlp/SWE-agent/pull/420)
* Web UI: Render Markdown in agent feed messages. by [@kwight](https://github.com/kwight) in [#486](https://github.com/princeton-nlp/SWE-agent/pull/486)
* Enh: Remove redundant 'saved traj to X' messages by [@klieret](https://github.com/klieret) in [#528](https://github.com/princeton-nlp/SWE-agent/pull/528)
* Allow to disable config dump to log by [@klieret](https://github.com/klieret) in [#537](https://github.com/princeton-nlp/SWE-agent/pull/537)
* Resolve relative paths to demonstrations and commands by [@klieret](https://github.com/klieret) in [#444](https://github.com/princeton-nlp/SWE-agent/pull/444)

### Fixed

* Web UI: Remove -n option to wait by [@klieret](https://github.com/klieret) in [#487](https://github.com/princeton-nlp/SWE-agent/pull/487)
* Web UI: Kill the Flask server on exit. by [@kwight](https://github.com/kwight) in [#479](https://github.com/princeton-nlp/SWE-agent/pull/479)
* Web UI: Avoid proxy errors on MacOS by [@klieret](https://github.com/klieret) in [#506](https://github.com/princeton-nlp/SWE-agent/pull/506)
* Ensure container_name is reset for non-persistent containers by [@klieret](https://github.com/klieret) in [#463](https://github.com/princeton-nlp/SWE-agent/pull/463)
* Fix: Do not allow persistent container with cache task imgs by [@klieret](https://github.com/klieret) in [#551](https://github.com/princeton-nlp/SWE-agent/pull/551)


## 0.5.0 (2024-05-28)

[All new commits](https://github.com/SWE-agent/SWE-agent/compare/v0.4.0...v0.5.0)

✨ The big news is our [brand new documentation](https://swe-agent.com/latest/) ✨

Secondly, [@ollmer](https://github.com/ollmer) added a new flag `--cache_task_images` that will significantly speed up SWE-agent when running on the same environment/repository multiple times (no more waiting for cloning and installation!)

### Breaking changes

* We have reformatted our codebase. If you create a PR based on a previous commit, make sure you install our `pre-commit` hook to avoid merge-conflicts because of formatting. See [our docs](https://swe-agent.com/latest/dev/formatting_conflicts/) for more information.
* Remove direct imports in `__init__.py` (you can no longer `from sweagent import Agent` by [@klieret](https://github.com/klieret) in [#436](https://github.com/princeton-nlp/SWE-agent/pull/436)

### Added

* Running the web UI is now supported when running SWE-agent completely in docker
* Speed up evaluation by caching task environments as docker images by [@ollmer](https://github.com/ollmer) in [#317](https://github.com/princeton-nlp/SWE-agent/pull/317)

### Improved

* Add gpt-4o model by [@raymyers](https://github.com/raymyers) in [#344](https://github.com/princeton-nlp/SWE-agent/pull/344)
* Web: Allow to specify commit hash by [@klieret](https://github.com/klieret) in [#358](https://github.com/princeton-nlp/SWE-agent/pull/358)
* Add default environment_setup config by [@klieret](https://github.com/klieret) in [#351](https://github.com/princeton-nlp/SWE-agent/pull/351)
* Enh: Suppress openai logging; improve formatting of stats by [@klieret](https://github.com/klieret) in [#416](https://github.com/princeton-nlp/SWE-agent/pull/416)
* Remove signal dependency by [@klieret](https://github.com/klieret) in [#428](https://github.com/princeton-nlp/SWE-agent/pull/428)
* Do not use select if running on Windows by [@klieret](https://github.com/klieret) in [#429](https://github.com/princeton-nlp/SWE-agent/pull/429)
* Use custom Config class to support env and keys.cfg (this allows passing keys as environment variables) by [@klieret](https://github.com/klieret) in [#430](https://github.com/princeton-nlp/SWE-agent/pull/430)

### Fixed

* Web: Fix script_path input by [@klieret](https://github.com/klieret) in [#334](https://github.com/princeton-nlp/SWE-agent/pull/334)
* Fix: Don't print patch msg for exit_cost patch by [@klieret](https://github.com/klieret) in [#343](https://github.com/princeton-nlp/SWE-agent/pull/343)
* Fix: Do not request job control in bash by [@klieret](https://github.com/klieret) in [#345](https://github.com/princeton-nlp/SWE-agent/pull/345)
* Fix: --base_commit not used for gh urls by [@klieret](https://github.com/klieret) in [#346](https://github.com/princeton-nlp/SWE-agent/pull/346)
* Fix: Separate data path/traj dir cause exception by [@klieret](https://github.com/klieret) in [#348](https://github.com/princeton-nlp/SWE-agent/pull/348)
* Add docker-py lower bound by [@klieret](https://github.com/klieret) in [#406](https://github.com/princeton-nlp/SWE-agent/pull/406)
* Fix: IndexError when replaying incomplete trajectories by [@klieret](https://github.com/klieret) in [#410](https://github.com/princeton-nlp/SWE-agent/pull/410)


## 0.4.0 (2024-05-09)

[All new commits](https://github.com/SWE-agent/SWE-agent/compare/v0.3.0...v0.4.0)

### Added

We’re excited to launch the SWE-agent web UI! Specify a bug, press start and watch SWE-agent do the magic.

## 0.3.0 (2024-05-02)

### Added

* Run SWE-agent in the cloud using GitHub Codespaces
* Add GPT4-turbo model by [@zgrannan](https://github.com/zgrannan) in [#252](https://github.com/princeton-nlp/SWE-agent/pull/252)
* feat: Amazon Bedrock support (Claude models) by [@JGalego](https://github.com/JGalego) in [#207](https://github.com/princeton-nlp/SWE-agent/pull/207)

### Fixed

* Better error handling for --open_pr by [@klieret](https://github.com/klieret) in [#239](https://github.com/princeton-nlp/SWE-agent/pull/239)
* Fixed a potential error by [@DanjieTang](https://github.com/DanjieTang) in [#242](https://github.com/princeton-nlp/SWE-agent/pull/242)
* fix: TARGETARCH not set on some OS/docker setups by [@mspronesti](https://github.com/mspronesti) in [#249](https://github.com/princeton-nlp/SWE-agent/pull/249)
* Pass Python version to get_environment_yml by [@waterson](https://github.com/waterson) in [#271](https://github.com/princeton-nlp/SWE-agent/pull/271)
* Fix Together model validation error by [@mikanfactory](https://github.com/mikanfactory) in [#236](https://github.com/princeton-nlp/SWE-agent/pull/236)
* Doc: Avoid invalid github token by [@klieret](https://github.com/klieret) in [#292](https://github.com/princeton-nlp/SWE-agent/pull/292)

## 0.2.0 (2024-04-15)

[All new commits](https://github.com/SWE-agent/SWE-agent/compare/v0.1.2...v0.2.0)

### Added

* Allow to run on local repos (new flag: `--repo_path`) in [#193](https://github.com/princeton-nlp/SWE-agent/pull/193)
* Patch files are now saved separately to a patch directory in [#126](https://github.com/princeton-nlp/SWE-agent/pull/126)
* Allow to supply custom installation commands when running on gh issues or locally (`--environment_setup`) in [#153](https://github.com/princeton-nlp/SWE-agent/pull/153)
* Allow to specify openapi base url in `keys.cfg` in [#118](https://github.com/princeton-nlp/SWE-agent/pull/118)

### Improved

* Improve error handling of docker issues in [#165](https://github.com/princeton-nlp/SWE-agent/pull/165)
* Make github token fully optional in [#189](https://github.com/princeton-nlp/SWE-agent/pull/189)

### Fixed

* Fix opening PR from fork in [#229](https://github.com/princeton-nlp/SWE-agent/pull/229)
* Fix: Choosing TogetherAI models in [#130](https://github.com/princeton-nlp/SWE-agent/pull/130)
