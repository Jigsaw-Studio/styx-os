# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY relay.py .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir requests

# Make UDP port 8192 available to the world outside this container
EXPOSE 8192/udp

# Run relay.py when the container launches
CMD ["python", "-u", "./relay.py"]
