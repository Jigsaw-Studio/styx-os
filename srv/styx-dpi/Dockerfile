# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install tcpdump and other necessary packages
RUN apt-get update && apt-get install -y tcpdump nbtscan gcc

# Copy the current directory contents into the container at /app
COPY dpi.py .
COPY requirements.txt ./requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Run process.py when the container launches
ENTRYPOINT ["python", "dpi.py"]
