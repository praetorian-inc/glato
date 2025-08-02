FROM python:3.9-alpine AS builder

# Install required system dependencies
RUN apk add --no-cache git gcc musl-dev libffi-dev openssl-dev

# Set working directory
WORKDIR /build

# Args for GitHub authentication
ARG GITHUB_TOKEN

# Clone the repository using the token for authentication
RUN git clone https://${GITHUB_TOKEN}@github.com/praetorian-inc/glato.git .

# Install glato in a way that prepares for copying to the final image
RUN pip install --no-cache-dir --prefix=/install .

# Start a new stage with a clean image
FROM python:3.9-alpine

# Install runtime dependencies
RUN apk add --no-cache libffi openssl

# Copy the installed application from the builder stage
COPY --from=builder /install /usr/local

# Create config directory for cookie configuration
RUN mkdir -p /app/glato/config

# Set working directory
WORKDIR /app

# Set entrypoint to glato
ENTRYPOINT ["glato"]

# Default command (will be appended to entrypoint)
CMD ["--help"]