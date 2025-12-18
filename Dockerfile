FROM python:3.12

WORKDIR /code

# Copy only requirements first to leverage caching
COPY requirements.txt /code/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install "fastapi[standard]"
# Copy the rest of the code
COPY . /code

# Set environment variable
ENV PYTHONPATH=/code

# Expose the port (optional but recommended)
EXPOSE 8071

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8071"]
