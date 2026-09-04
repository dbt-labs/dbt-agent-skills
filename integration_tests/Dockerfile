FROM node:20-alpine

WORKDIR /workspace

# Install shell/runtime dependencies and Claude Code CLI
RUN apk add --no-cache bash jq && \
    npm install -g @anthropic-ai/claude-code

# Copy plugin structure
COPY skills/ skills/

# Copy test scripts
COPY integration_tests/*.sh /workspace/integration_tests/
RUN chmod +x /workspace/integration_tests/*.sh

# Run integration tests for all plugins during build
RUN /workspace/integration_tests/run.sh

RUN addgroup -S app && adduser -S -G app app && chown -R app:app /workspace

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD claude --version >/dev/null 2>&1 || exit 1

USER app

CMD ["/workspace/integration_tests/docker-entrypoint.sh"]
