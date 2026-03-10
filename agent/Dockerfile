FROM python:3.11-slim

# Set environment variables for optimized Python execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Create a virtual environment
RUN python -m venv /app/.venv

# Copy and install requirements into the virtual environment
COPY requirements.txt .
RUN . /app/.venv/bin/activate && pip install --no-cache-dir -r requirements.txt

# The agent-src directory is mounted as read-only volume in docker-compose
# We copy it to /app so we can run it, but hot-swaps happen by updating /app/scraper.py
COPY scraper.py .

EXPOSE 8000

# Added --reload for hot-swapping scraper.py without needing to manually restart the container
CMD ["uvicorn", "scraper:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
