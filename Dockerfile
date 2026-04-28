FROM python:3.11-slim

EXPOSE 5000

# Install system dependencies
RUN apt-get update && \
    apt-get -y upgrade --no-install-recommends --no-install-suggests && \
    apt-get -y install --no-install-recommends --no-install-suggests \
        wget \
        curl \
        nano

# Install Poetry
RUN pip install --upgrade pip && \
    pip install poetry

# # Install LDF Package using Poetry with secret token
WORKDIR /app
COPY . .

# Instal LDF package + dependencies (production)
RUN --mount=type=secret,id=GIT_AUTH_TOKEN \
    # pip install --extra-index-url https://Dienstkonto.Buildbot:$(cat < /run/secrets/GIT_AUTH_TOKEN)@ccp-tea.lawo.de/api/packages/quality-assurance/pypi/simple/ lawo-device-factory 
    poetry config http-basic.gitea-pypi x-access-token $(cat < /run/secrets/GIT_AUTH_TOKEN) && \
    poetry config virtualenvs.create false && \
    poetry install --no-root

# Build LDF API Documentation
# RUN mkdir -p docs/build/html/
RUN poetry run sphinx-apidoc -o docs/source/ ldf 
RUN poetry run sphinx-build -b html docs/source/ docs/build/html/

# Cleanup apt
RUN apt-get -y autoremove -o APT::Autoremove::RecommendsImportant=0 -o APT::Autoremove::SuggestsImportant=0 --purge && \
    rm -rf /var/lib/apt/lists/*

# Run app to expose API docs by default
CMD ["poetry", "run", "python", "app.py"]