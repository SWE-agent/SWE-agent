---
title: "Getting Started"
---

<div style="text-align: center;">
    <img class="light-mode-only" src="assets/readme_assets/swe-agent-banner-light.svg" alt="SWE-agent banner" style="height: 10em;">
    <img class="dark-mode-only" src="assets/readme_assets/swe-agent-banner-dark.svg" alt="SWE-agent banner" style="height: 10em;">
</div>

SWE-agent lets your language model of choice (e.g. GPT-4o or Claude Sonnet 3.5) autonomously use tools to:

* [fix issues in real GitHub repositories](usage/hello_world.md),
* perform tasks on the web,
* crack cybersecurity challenges, or
* [any custom task](usage/coding_challenges.md).

It does so by using configurable [agent-computer interfaces](https://arxiv.org/abs/2405.15793) (ACIs) to interact with isolated computer environments.
SWE-agent uses [SWE-ReX](https://swe-rex.com/) for sandboxed code execution.

<div class="grid cards" markdown>



-   :material-download:{ .lg .middle } __Installation__

    ---

    Installing SWE-agent.

    [:octicons-arrow-right-24: Get started](installation/index.md)


-   :material-cog:{ .lg .middle } __Hello world__

    ---

    Solve a GitHub issue with SWE-agent.

    [:octicons-arrow-right-24: Hello world](usage/hello_world.md)


-   :material-lightbulb:{ .lg .middle } __User guides__

    ---

    Dive deeper into SWE-agent's features and goals.

    [:octicons-arrow-right-24: User guides](usage/index.md)


-   :material-book:{ .lg .middle } __Background & goals__

    ---

    Learn more about the project goals and academic research.

    [:octicons-arrow-right-24: Learn more](background/index.md)

</div>

## 📣 News

* May 2: [SWE-agent-LM-32b](https://swesmith.com) achieves open-weights SOTA on SWE-bench
* Feb 28: [SWE-agent 1.0 + Claude 3.7 is SoTA on SWE-Bench full](https://x.com/KLieret/status/1895487966409298067)
* Feb 25: [SWE-agent 1.0 + Claude 3.7 is SoTA on SWE-bench verified](https://x.com/KLieret/status/1894408819670733158)
* Feb 13: [Releasing SWE-agent 1.0: SoTA on SWE-bench light & tons of new features](https://x.com/KLieret/status/1890048205448220849)
* Dec 7: [An interview with the SWE-agent & SWE-bench team](https://www.youtube.com/watch?v=fcr8WzeEXyk)

## ✍️ Doc updates

* Apr 8: [Running SWE-agent competitively](usage/competitive_runs.md)
* Mar 7: [Updated SWE-agent architecture diagram of 1.0](background/architecture.md)