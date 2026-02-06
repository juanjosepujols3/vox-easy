FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY web/ web/
COPY api.py .
COPY db.py .
COPY models.py .
COPY auth.py .

# Environment variables
ENV DATABASE_URL=postgresql+asyncpg://postgres:trijilio0397@unicords_voxeasy-db:5432/unicords
ENV JWT_SECRET=voxeasy-secret-change-in-production
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
