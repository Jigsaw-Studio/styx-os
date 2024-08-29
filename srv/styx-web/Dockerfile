# Official lightweight image for Nginx on ARM
FROM nginx:alpine

# Install openssl
RUN apk add --no-cache openssl

# Environment variables with default values
ENV DAYS_VALID="365" \
    CERT_DIR="/etc/nginx/certs" \
    CERT_KEY="nginx.key" \
    CERT_CRT="nginx.crt" \
    COUNTRY="US" \
    STATE="California" \
    LOCALITY="San Francisco" \
    ORGANIZATION="Jigsaw Studios" \
    COMMON_NAME="localhost"

# Set the working directory
WORKDIR /usr/share/nginx/html

# Remove the default Nginx configuration file
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom Nginx configuration file
COPY etc/nginx/conf.d/nginx.conf /etc/nginx/conf.d

# Create the directory for certificates, and generate the self-signed certificate
RUN mkdir -p "${CERT_DIR}" && \
    openssl req -x509 -nodes -days "${DAYS_VALID}" -newkey rsa:2048 \
    -keyout "${CERT_DIR}"/"${CERT_KEY}" -out "${CERT_DIR}"/"${CERT_CRT}" \
    -subj "/C=${COUNTRY}/ST=${STATE}/L=${LOCALITY}/O=${ORGANIZATION}/CN=${COMMON_NAME}"

# Expose HTTP and HTTPS
EXPOSE 80 443

# Start Nginx when the container starts
CMD ["nginx", "-g", "daemon off;"]
