# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Inform Docker that the container is listening on the specified port at runtime.
# Railway usually provides the PORT environment variable.
EXPOSE 8080

# Run server.py when the container launches
CMD ["python", "server.py"]
