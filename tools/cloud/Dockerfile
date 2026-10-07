# Minimal, production-ready Dockerfile optimized for Google Cloud Run & Local Docker
# Cold-start target < 3s with lightweight Python base image

FROM python:3.11-slim

# Set environment variables for Cloud Run runtime & Python optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DEBIM_NO_UPDATE_CHECK=1

WORKDIR /app

# Install minimal OS runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy project files & install debim with all optional dependencies
COPY . /app
RUN pip install --no-cache-dir ".[all]"

# Expose default Cloud Run HTTP port
EXPOSE 8080

# Entrypoint runs debim CLI / Cloud ephemeral runner or MCP server
ENTRYPOINT ["debim"]
CMD ["mcp"]
