FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY pyproject.toml .
RUN pip install uv && uv pip install --system -r pyproject.toml

# install Playwright browsers
RUN playwright install chromium

COPY . .
