FROM python:3.11-slim

WORKDIR /app

# Install minimal build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy repository files and install debim with MCP & IFC dependencies
COPY . /app
RUN pip install --no-cache-dir -e ".[all]"

# Entrypoint runs debim Model Context Protocol server over stdio
ENTRYPOINT ["debim", "mcp"]
