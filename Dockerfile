# Stage 1: Build the index
FROM python:3.10-slim as builder

WORKDIR /app

# Install system dependencies required for easyocr
RUN apt-get update && apt-get install -y libgl1

# Set cache directory for huggingface
ENV HF_HOME /app/huggingface_cache
RUN mkdir -p /app/huggingface_cache && chmod -R 777 /app/huggingface_cache

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY data/ ./data/
COPY build_index.py .
COPY storage/ ./storage/
# RUN python build_index.py

# Stage 2: Run the application
FROM python:3.10-slim

WORKDIR /app

# Set cache directories
ENV LLAMA_INDEX_CACHE_DIR /app/cache
ENV HF_HOME /app/huggingface_cache
RUN mkdir -p /app/cache /app/huggingface_cache && chmod -R 777 /app/cache /app/huggingface_cache

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and assets
COPY app.py .
COPY static/ ./static/
COPY --from=builder /app/storage/ ./storage/
COPY --from=builder /app/data/ ./data/

# Create and set permissions for the logs directory
RUN mkdir -p /app/logs && chmod -R 777 /app/logs

# Expose the port the app runs on
EXPOSE 7860

# Command to run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
