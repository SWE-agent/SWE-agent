FROM python:3.13-slim

# Set the working directory
WORKDIR /app

# Install nodejs
RUN apt update && \
    apt install -y nodejs npm curl && \
    # Install Docker CLI using the official Docker installation script
    curl -fsSL https://get.docker.com -o get-docker.sh && \
    sh get-docker.sh && \
    rm get-docker.sh && \
    apt remove -y curl && \
    apt autoremove -y && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the application code
# Do this last to take advantage of the docker layer mechanism
COPY . /app

# Install Python dependencies
RUN pip install -e '.'

# Install react dependencies ahead of time
RUN cd sweagent/frontend && npm install
