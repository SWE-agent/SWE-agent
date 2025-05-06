# Environments

SWE-agent runs on docker images (`python:3.11` by default).
If you are running on SWE-Benmch, every instance has a docker image that we pull from dockerhub.

Here's an example of a simple custom docker environment:

```dockerfile title="tiny.Dockerfile"
FROM python:3.11.10-bullseye  # (1)!

ARG DEBIAN_FRONTEND=noninteractive  # (2)!
ENV TZ=Etc/UTC

WORKDIR /

# Install swe-rex for faster startup
RUN pip install pipx
RUN pipx install swe-rex
RUN pipx ensurepath
ENV PATH="$PATH:/root/.local/bin/"

# Install any extra dependencies
RUN pip install flake8

SHELL ["/bin/bash", "-c"]
```

1. This is the base image that we're starting from
2. Important to disable any interactive prompts when installing things

Build it with `docker build -f tiny.Dockerfile -t swe-agent-tiny .`.

Now you can run it in the agent with `sweagent run --env.image swe-agent-tiny ...`
