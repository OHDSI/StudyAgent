FROM mambaorg/micromamba:2.5-alpine3.22

USER root
WORKDIR /app

RUN apk add --no-cache curl

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes

COPY --chown=$MAMBA_USER:$MAMBA_USER core/ ./core/
COPY --chown=$MAMBA_USER:$MAMBA_USER mcp_server/ ./mcp_server/
COPY --chown=$MAMBA_USER:$MAMBA_USER acp_agent/ ./acp_agent/
COPY --chown=$MAMBA_USER:$MAMBA_USER docs/ ./docs/
COPY --chown=$MAMBA_USER:$MAMBA_USER README.md ./
COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml ./

RUN micromamba run -n base pip install --no-cache-dir -e .

RUN mkdir -p /data/phenotype_index && chown -R $MAMBA_USER:$MAMBA_USER /data

USER $MAMBA_USER

ENV PYTHONUNBUFFERED=1 \
    PHENOTYPE_INDEX_DIR=/data/phenotype_index \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8790 \
    MCP_PATH=/mcp \
    STUDY_AGENT_HOST=0.0.0.0 \
    STUDY_AGENT_PORT=8765 \
    STUDY_AGENT_HOST_GATEWAY=host.docker.internal \
    STUDY_AGENT_MCP_URL=http://host.docker.internal:8790/mcp

CMD ["micromamba", "run", "-n", "base", "study-agent-mcp"]
