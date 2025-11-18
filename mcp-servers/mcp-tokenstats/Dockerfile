FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Cloud Run uses PORT environment variable (defaults to 8080)
# The server.py reads PORT from environment
ENV PORT=8080

# Expose port (Cloud Run will override this)
EXPOSE 8080

# Run the server using uvicorn
# Cloud Run sets PORT automatically, server.py reads it
CMD exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}

