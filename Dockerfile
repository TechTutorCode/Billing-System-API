FROM python:3.12-slim

WORKDIR /code

# Install Python dependencies
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install "fastapi[standard]" PyJWT

# Copy the app code
COPY . /code

ENV PYTHONPATH=/code

# Copy VPN script into container
COPY ovpn-user.sh /usr/local/bin/ovpn-user.sh
RUN chmod +x /usr/local/bin/ovpn-user.sh

# Ensure OpenVPN psw-file exists
RUN mkdir -p /etc/openvpn \
    && touch /etc/openvpn/psw-file \
    && chmod 660 /etc/openvpn/psw-file \
    && chown root:root /etc/openvpn/psw-file


# Expose FastAPI port
EXPOSE 8071

# Run app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8071"]
