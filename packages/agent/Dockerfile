FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    patch \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY packages/agent/hermes_data/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Copy agent scripts and patches
COPY packages/agent/scripts /app/scripts
COPY packages/agent/patches /app/patches

# Apply patches to the installed hermes-agent
RUN python /app/scripts/patch_dependencies.py

# Set environment variables with defaults
ENV HERMES_PROJECT_ROOT=/app
ENV HERMES_DATA_DIR=/app/.tmp
ENV HERMES_DB_FILE=local.db

# Create directories
RUN mkdir -p /app/.tmp /app/logs /app/scripts/hermes_data/on_call_logs

# Make scripts executable
RUN chmod +x /app/scripts/on_call/*.py

# Expose webhook port
EXPOSE 8678

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8678/health || exit 1

# Default command
CMD ["python", "-m", "scripts.on_call.reporter"]
