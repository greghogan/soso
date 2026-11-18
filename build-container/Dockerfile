# Build context is this directory only; manuscript data is mounted read-only at run time.
ARG BASE_IMAGE=python:3.12-slim-trixie
FROM ${BASE_IMAGE}
ARG DEBIAN_SNAPSHOT=""
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC SVG_PDF_CONVERTER=rsvg-convert
# Snapshot freshness checks are disabled only for intentionally historical snapshots;
# repository signatures and HTTPS remain enabled.
RUN if [ -n "$DEBIAN_SNAPSHOT" ]; then \
      rm -f /etc/apt/sources.list /etc/apt/sources.list.d/*; \
      printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s/ trixie main\n' "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list; \
    fi \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates fontconfig fonts-noto-core fonts-dejavu-core fonts-dejavu-extra \
      fonts-texgyre lmodern librsvg2-bin libjxl-tools \
      texlive-xetex texlive-latex-extra texlive-fonts-recommended \
 && rm -rf /var/lib/apt/lists/*
# Pin the multi-architecture uv image; Docker selects the host architecture.
COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv
COPY requirements.txt /opt/manual-builder/requirements.txt
# Install into the isolated image as root; run.sh runs document builds as the host user.
RUN uv pip install --system --no-cache -r /opt/manual-builder/requirements.txt \
 && fc-cache -f \
 && uv pip freeze --system > /opt/manual-builder/python-installed.txt \
 && dpkg-query -W > /opt/manual-builder/debian-installed.txt
COPY run_build.py /opt/manual-builder/run_build.py
WORKDIR /work
ENTRYPOINT ["python", "/opt/manual-builder/run_build.py"]
