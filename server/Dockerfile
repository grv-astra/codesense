# --- Stage 1: freeze the backend into a single compiled binary -------------
# Our own source (local/, scanner/, licenses/, common/, codesense/) never
# lands in the runtime image as plaintext .py -- only this frozen binary does.
# Reuses the existing codesense.spec (already proven on the Windows desktop
# build); running it here on Linux produces a Linux ELF instead of a .exe.
FROM python:3.13-slim AS freeze

RUN apt-get update && apt-get install -y --no-install-recommends binutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pyinstaller

COPY server/ .
RUN pyinstaller codesense.spec --noconfirm --clean
# -> /src/dist/codesense-server (onefile binary)

# --- Stage 2: runtime --------------------------------------------------------
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# syft, grype, grant (all Anchore) -- SBOM generation, vulnerability
# scanning, and license checking respectively. sbom_pipeline.py shells out
# to all three by bare name (tool_path()), not just grype.
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
      | sh -s -- -b /usr/local/bin
RUN curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh \
      | sh -s -- -b /usr/local/bin
RUN curl -sSfL https://raw.githubusercontent.com/anchore/grant/main/install.sh \
      | sh -s -- -b /usr/local/bin

# cosign (sigstore) -- SBOM signing. sbom_pipeline.py unconditionally passes
# --use-signing-config=false, a flag that only exists on cosign v3.x+ (it
# errors "unknown flag" on v2.4.x) -- must pin a v3.x release, not v2.4.x.
ARG COSIGN_VERSION=v3.0.6
RUN curl -sSfL -o /usr/local/bin/cosign \
      "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64" \
    && chmod +x /usr/local/bin/cosign

# semgrep itself is a third-party OSS tool (not our IP) -- installed as a
# normal pip package so its `semgrep` console-script is on PATH. Our own code
# is NOT installed as source here; only the frozen binary below is.
RUN pip install --no-cache-dir "semgrep>=1.90,<2"

WORKDIR /app
COPY --from=freeze /src/dist/codesense-server /app/codesense-server

# Bundled offline Semgrep rules (public OSS rule pack, not proprietary --
# checked into docker/assets/ since dist/ itself is gitignored).
COPY docker/assets/semgrep-rules.zip /tmp/semgrep-rules.zip
RUN mkdir -p /app/vendor && \
    unzip -q /tmp/semgrep-rules.zip -d /app/vendor && \
    rm /tmp/semgrep-rules.zip && \
    rm -rf /app/vendor/semgrep-rules/.git
ENV SEMGREP_RULES_DIR=/app/vendor/semgrep-rules

# Bundled Grype vulnerability DB snapshot -- avoids a live `grype db update`
# at scan time, which a network-restricted client VM couldn't do anyway.
# Frozen/no-auto-update at runtime, same pattern as the offline desktop build.
COPY dist/grype-db /app/vendor/grype-db
ENV GRYPE_DB_CACHE_DIR=/app/vendor/grype-db

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

EXPOSE 8585

CMD ["/app/codesense-server", "0.0.0.0", "8585"]
