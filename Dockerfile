# Use an official Python runtime as a parent image.
FROM python:3.9-slim

# Install system dependencies, including ffmpeg (which includes ffprobe).
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container.
WORKDIR /app

# Copy the requirements file and install Python dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the environment file into the container.
COPY keys.env ./

# Copy your application code into the container.
COPY crawler.py ./
COPY twitter_poster.py ./
# (If you have additional modules or folders, copy them as well.)
# COPY other_module.py ./

# Expose port 8000 (or whichever port your app uses).
EXPOSE 8000

# Run your FastAPI app using Uvicorn.
CMD ["uvicorn", "crawler:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]
