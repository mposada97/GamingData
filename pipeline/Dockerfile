#starts with light weight python 3.14 
FROM python:3.14.3-slim
#installs uv 
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# creates code folder and sets it as working directory
WORKDIR /code
#adds the venv bin folder to system path
ENV PATH="/code/.venv/bin:$PATH"

#copies metadata uv files needed to reproduce environment
COPY pyproject.toml .python-version uv.lock ./
#runs uv sync to install dependencies
RUN uv sync --locked

#files will be mounted through docker compose yaml
