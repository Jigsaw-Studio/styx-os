# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY api.py ./
COPY requirements.txt ./requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the API will run on
EXPOSE 8192

# Run api.py when the container launches
ENTRYPOINT ["python", "api.py"]
