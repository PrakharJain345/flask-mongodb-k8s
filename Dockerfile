FROM python:3.9-slim

WORKDIR /app

# Install dependencies first for Docker layer caching
COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/app.py app.py

# Create a non-root user and switch to it
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "2", "app:app"]

