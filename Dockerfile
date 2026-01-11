FROM python:3.12-slim

WORKDIR /code

# Copy only requirements first to leverage caching
COPY requirements.txt /code/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install "fastapi[standard]"
RUN pip install PyJWT

# Copy the rest of the code
COPY . /code

# Set environment variable
ENV PYTHONPATH=/code

# --- VPN Automation Setup ---

# Copy the ovpn-user.sh script into the container
COPY ovpn-user.sh /usr/local/bin/ovpn-user.sh
RUN chmod +x /usr/local/bin/ovpn-user.sh

# Ensure psw-file exists for OpenVPN (will mount host file later)
RUN mkdir -p /etc/openvpn && \
    touch /etc/openvpn/psw-file && \
    chmod 600 /etc/openvpn/psw-file

# Expose the port
EXPOSE 8071

# Run the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8071"]
