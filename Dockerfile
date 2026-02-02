# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage - distroless
FROM gcr.io/distroless/python3-debian12

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /root/.local /root/.local

# Copy application files
COPY flight_tracker.py /app/
COPY config.json /app/

WORKDIR /app

# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib/python3.11/site-packages:/usr/local/lib/python3.11/site-packages
ENV PYTHONUNBUFFERED=1

# Expose port for status web server
EXPOSE 8080

# Run the application
ENTRYPOINT ["python", "flight_tracker.py"]
