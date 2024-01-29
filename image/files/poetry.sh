if [ -d /opt/poetry/bin ]; then
    export PATH="/opt/poetry/bin:${PATH}"
fi

if [ -d /opt/vintage-pi-tv/.venv/bin ]; then
    export PATH="/opt/vintage-pi-tv/.venv/bin:${PATH}"
fi
