# Dockerfile for promptctl with Ollama integration
# Provides complete DSPy automation pipeline with LLM support
#
# Usage:
#   docker-compose up -d
#   # Extension connects to http://localhost:9090

FROM ollama/ollama:latest

# Install Python and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    git \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Python packages directly (not using venv since base image has different Python)
RUN pip3 install --break-system-packages --no-cache-dir --timeout 300 \
    GitPython requests dspy-ai || true

# Create promptctl user and directories (UID 1001 to avoid conflict with ollama base image)
RUN useradd -m -u 1001 -s /bin/bash promptctl && \
    mkdir -p /home/promptctl/.promptctl && \
    mkdir -p /var/log/promptctl && \
    mkdir -p /root/.ollama && \
    chown -R promptctl:promptctl /home/promptctl /var/log/promptctl

# Set up application directory
WORKDIR /app
COPY . /app
RUN chown -R promptctl:promptctl /app

# Configure git for both users (root for ollama, promptctl for app)
RUN git config --global user.name "promptctl" && \
    git config --global user.email "promptctl@localhost" && \
    git config --global --add safe.directory /home/promptctl/.promptctl && \
    git config --global --add safe.directory '*'

ENV PYTHONUNBUFFERED=1
ENV PROMPTCTL_REPO=/home/promptctl/.promptctl

# Ollama configuration
ENV OLLAMA_HOST=0.0.0.0:11434
ENV OLLAMA_MODELS=/root/.ollama/models

# Copy entrypoint and supervisor config
COPY docker-entrypoint.sh /usr/local/bin/
COPY supervisord.conf /etc/supervisor/conf.d/promptctl.conf
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose ports: 9090 for promptctl socket, 11434 for Ollama API
EXPOSE 9090 11434

# Volumes for persistent data
VOLUME ["/home/promptctl/.promptctl", "/root/.ollama"]

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["auto"]
