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
        # Tools I like to use for development
        command-not-found \
        less \
        nano \
        procps \
        wget \
    # Don't delete package index, since we're developing here
    && apt-file update

# Install noVNC to nginx root
RUN rm -rf /var/www/html \
    && ln -s /usr/share/novnc /var/www/html \
    && ln -s /usr/share/novnc/vnc.html /usr/share/novnc/index.html

# Install poetry
ARG POETRY_VERSION=1.7.1 \
    POETRY_HOME=/opt/poetry
RUN curl -L https://install.python-poetry.org/ | python3
ENV PATH="${POETRY_HOME}/bin:${PATH}"

# Add basic files needed for poetry (need vintage_pi_tv/__init__.py to install poetry scripts)
RUN mkdir -p /app/vintage_pi_tv && touch /app/vintage_pi_tv/__init__.py
WORKDIR /app
COPY pyproject.toml poetry.lock /app/

# Install deps (comment out readme in pyproject to prevent failure)
RUN sed -i 's/^readme = /#\0/' pyproject.toml && poetry install --without=keyboard

# Set up entrypoint which stats Xvfb, x11vnc and nginx serving noVNC
ENV DISPLAY=:0
ENTRYPOINT [ "/entrypoint.sh" ]
CMD [ "/bin/sh", "-c", "while ! [ -S /tmp/.X11-unix/X0 ]; do sleep 0.05 ; done ; exec tv --reload" ]
