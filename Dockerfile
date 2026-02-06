FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY engine/ engine/
COPY web/ web/
COPY api.py .
COPY db.py .
COPY models.py .
COPY auth.py .

# Create models directory for Whisper
RUN mkdir -p models

# Pre-download the Whisper model during build
RUN python -c "from engine.transcriber import Transcriber; Transcriber(model_size='tiny')"

# Environment variables
ENV WHISPER_MODEL=tiny
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8
ENV DATABASE_URL=postgresql+asyncpg://postgres:trijilio0397@unicords_voxeasy-db:5432/unicords
ENV JWT_SECRET=voxeasy-secret-change-in-production
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
