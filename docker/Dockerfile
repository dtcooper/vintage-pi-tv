FROM debian:bookworm

# Add dependencies
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        libmpv2 \
        mpv \
        nginx \
        novnc \
        python-is-python3 \
        python3 \
        supervisor \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install noVNC to nginx root
RUN rm -rf /var/www/html \
    && ln -s /usr/share/novnc /var/www/html \
    && ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# Install poetry
ARG POETRY_VERSION=1.7.1 \
    POETRY_HOME=/opt/poetry
RUN curl -L https://install.python-poetry.org/ | python3
ENV PATH="${POETRY_HOME}/bin:${PATH}"

# Add basic files needed for poetry
RUN mkdir -p /app/vintage_pi_tv \
    && touch /app/README.md /app/vintage_pi_tv/__init__.py
WORKDIR /app
COPY pyproject.toml poetry.lock /app/

# Install deps
RUN poetry install

# Copy over image files
COPY docker/entrypoint.sh /
COPY docker/daemons.conf /etc/supervisor/conf.d/
COPY docker/nginx.conf /etc/nginx/sites-enabled/default

# Set up entrypoint which stats Xvfb, x11vnc and nginx serving noVNC
ENV DISPLAY=:0
ENTRYPOINT [ "/entrypoint.sh" ]
CMD [ "/bin/bash" ]
