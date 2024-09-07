# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY relay.py .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir requests

# Set environment variable for UDP port, with default value of 8192
ENV UDP_PORT 8192

# Make the UDP port available to the world outside this container
EXPOSE ${UDP_PORT}/udp

# Run relay.py when the container launches, passing the UDP port as a command-line argument
CMD ["python", "-u", "./relay.py", "--port", "${UDP_PORT}"]
