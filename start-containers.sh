#!/bin/bash

# Script to detect the host IP and run Docker Compose on macOS/Linux

echo "Attempting to detect Host IP..."

# --- IP Detection --- 
# Method 1: Try common macOS interface (en0 for Wi-Fi/Ethernet)
HOST_IP=$(ifconfig en0 | grep 'inet ' | awk '{print $2}')

# Method 2: If en0 didn't work, try finding the default route's interface (more Linux-like)
if [ -z "$HOST_IP" ]; then
    echo "Method 1 (ifconfig en0) failed, trying Method 2 (ip route)..."
    DEFAULT_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n 1)
    if [ -n "$DEFAULT_INTERFACE" ]; then
        HOST_IP=$(ip addr show $DEFAULT_INTERFACE | grep "inet\b" | awk '{print $2}' | cut -d/ -f1)
    fi
fi

# Method 3: Fallback - Find first non-loopback, non-docker IP (less reliable)
if [ -z "$HOST_IP" ]; then
    echo "Method 2 failed, trying Method 3 (fallback)..."
    HOST_IP=$(ip addr | grep "inet\b" | grep -v "127\.0\.0\.1" | grep -v "inet 172\." | awk '{print $2}' | cut -d/ -f1 | head -n 1)
fi

# --- Validation --- 
if [ -z "$HOST_IP" ]; then
    echo "Error: Could not automatically detect a suitable host IP address." >&2
    echo "Please find your local network IP (e.g., using 'ifconfig' or System Preferences) and set it manually:" >&2
    echo "export HOST_IP=<your_ip_address>" >&2
    echo "Then run: docker-compose up -d --build" >&2
    exit 1
fi

echo "Using Host IP: $HOST_IP (This should be your Wi-Fi/LAN IP)"

# --- Docker Compose --- 
# Export the variable so docker-compose can use it
export HOST_IP

echo "Starting Docker containers with HOST_IP=$HOST_IP... (including build)"

# Run Docker Compose, forcing a rebuild of images if necessary
docker-compose up -d --build

# Check the exit code of the docker-compose command
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "Docker containers started successfully."
else
    echo "Error: Docker Compose failed to start containers. Exit code: $EXIT_CODE" >&2
    exit $EXIT_CODE
fi

exit 0 