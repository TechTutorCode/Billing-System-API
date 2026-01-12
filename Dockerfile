FROM python:3.12-slim

WORKDIR /code

# Install Python dependencies and OpenSSH client for SSH access to host
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install "fastapi[standard]" PyJWT

# Install OpenSSH client for SSH access to host machine
RUN apt-get update && apt-get install -y openssh-client && rm -rf /var/lib/apt/lists/*

# Copy the app code
COPY . /code

ENV PYTHONPATH=/code

# Expose FastAPI port
EXPOSE 8071

# Run app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8071"]
