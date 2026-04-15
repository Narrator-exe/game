FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["npc-sim"]
