FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for Docker layer caching
COPY lead-qualification-agent/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire app
COPY lead-qualification-agent/ ./

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
