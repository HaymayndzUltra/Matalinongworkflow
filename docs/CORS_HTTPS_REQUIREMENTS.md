# CORS & HTTPS Requirements
## API Security Configuration Guide

### Document Version
- **Version:** 1.0.0
- **Date:** 2025-01-16
- **Status:** Active
- **Compliance:** OWASP, RFC 6797, W3C CORS

---

## 1. HTTPS/TLS REQUIREMENTS

### 1.1 Minimum Standards
**MANDATORY ENFORCEMENT:**

| Component | Requirement | Rationale |
|-----------|------------|-----------|
| TLS Version | 1.3 minimum, 1.2 allowed | Security best practice |
| Certificate | Valid SSL from trusted CA | Trust establishment |
| Key Size | RSA 2048-bit or ECC 256-bit minimum | Cryptographic strength |
| HSTS | Enabled with 1-year max-age | Prevent downgrade attacks |
| Cipher Suites | Forward secrecy required | Future-proof security |

### 1.2 TLS Configuration

```nginx
# Nginx Configuration
server {
    listen 443 ssl http2;
    server_name api.example.com;
    
    # Certificate configuration
    ssl_certificate /etc/ssl/certs/api.example.com.crt;
    ssl_certificate_key /etc/ssl/private/api.example.com.key;
    
    # TLS versions
    ssl_protocols TLSv1.2 TLSv1.3;
    
    # Cipher suites (TLS 1.3)
    ssl_ciphers 'TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256';
    
    # Prefer server ciphers
    ssl_prefer_server_ciphers on;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    
    # Additional security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

### 1.3 Python/Flask HTTPS Setup

```python
# src/api/app.py
from flask import Flask
from flask_talisman import Talisman

app = Flask(__name__)

# Force HTTPS in production
if app.config.get('ENV') == 'production':
    Talisman(app, 
             force_https=True,
             strict_transport_security=True,
             strict_transport_security_max_age=31536000,
             session_cookie_secure=True,
             session_cookie_httponly=True,
             session_cookie_samesite='Strict')

# Development with self-signed cert
if __name__ == '__main__':
    app.run(ssl_context='adhoc', port=443)
```

---

## 2. CORS CONFIGURATION

### 2.1 CORS Policy Requirements

**STRICT ORIGIN CONTROL:**

| Header | Production Value | Development Value |
|--------|-----------------|-------------------|
| Access-Control-Allow-Origin | Specific origins only | localhost allowed |
| Access-Control-Allow-Methods | POST, GET, OPTIONS | Same |
| Access-Control-Allow-Headers | Content-Type, Authorization | Same |
| Access-Control-Max-Age | 86400 (24 hours) | 3600 (1 hour) |
| Access-Control-Allow-Credentials | true (if needed) | true |

### 2.2 Flask-CORS Implementation

```python
# src/api/app.py
from flask import Flask
from flask_cors import CORS
import os

app = Flask(__name__)

# Environment-based CORS configuration
if os.getenv('ENV') == 'production':
    # Production: Strict origins
    CORS(app, 
         origins=['https://app.example.com', 'https://mobile.example.com'],
         methods=['POST', 'GET', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'],
         max_age=86400,
         supports_credentials=True)
else:
    # Development: More permissive
    CORS(app,
         origins=['http://localhost:3000', 'http://localhost:8080'],
         methods=['POST', 'GET', 'OPTIONS', 'DELETE'],
         allow_headers=['Content-Type', 'Authorization', 'X-Debug-Token'],
         max_age=3600,
         supports_credentials=True)
```

### 2.3 Per-Endpoint CORS Control

```python
from flask import jsonify
from flask_cors import cross_origin

# Specific endpoint with custom CORS
@app.route('/face/lock/check', methods=['POST'])
@cross_origin(origins=['https://app.example.com'], 
              methods=['POST'],
              max_age=3600)
def check_face_lock():
    # Endpoint implementation
    return jsonify({'status': 'ok'})

# Public endpoint (metrics)
@app.route('/metrics', methods=['GET'])
@cross_origin(origins='*',  # Public access
              methods=['GET'],
              max_age=86400)
def get_metrics():
    # Return public metrics
    return jsonify({'metrics': get_public_metrics()})
```

---

## 3. PREFLIGHT REQUEST HANDLING

### 3.1 OPTIONS Method Implementation

```python
@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        # Build response for preflight
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = get_allowed_origin(request)
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age'] = '86400'
        
        if should_allow_credentials(request):
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        return response

def get_allowed_origin(request):
    """Validate and return allowed origin"""
    origin = request.headers.get('Origin')
    allowed_origins = app.config.get('ALLOWED_ORIGINS', [])
    
    if origin in allowed_origins:
        return origin
    return None  # Reject if not in whitelist
```

### 3.2 Complex Request Validation

```python
def validate_cors_request(request):
    """Validate CORS requirements for complex requests"""
    origin = request.headers.get('Origin')
    
    # Check origin whitelist
    if origin not in app.config['ALLOWED_ORIGINS']:
        return False, "Origin not allowed"
    
    # Check content type for POST
    if request.method == 'POST':
        content_type = request.headers.get('Content-Type', '')
        if not content_type.startswith('application/json'):
            return False, "Invalid content type"
    
    # Validate authorization if required
    if requires_auth(request.endpoint):
        auth = request.headers.get('Authorization')
        if not auth or not validate_token(auth):
            return False, "Invalid authorization"
    
    return True, "Valid"
```

---

## 4. SECURITY HEADERS

### 4.1 Required Security Headers

```python
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    
    # HSTS - Force HTTPS
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # XSS Protection (legacy browsers)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Content Security Policy
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'"
    
    # Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Permissions Policy
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    
    return response
```

### 4.2 API-Specific Headers

```python
@app.route('/face/burst/upload', methods=['POST'])
def upload_burst():
    response = jsonify(process_burst())
    
    # API versioning
    response.headers['X-API-Version'] = '1.0.0'
    
    # Rate limit headers
    response.headers['X-RateLimit-Limit'] = '100'
    response.headers['X-RateLimit-Remaining'] = get_remaining_quota()
    response.headers['X-RateLimit-Reset'] = get_reset_time()
    
    # Cache control for sensitive data
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response
```

---

## 5. CERTIFICATE MANAGEMENT

### 5.1 Certificate Requirements

| Aspect | Requirement | Implementation |
|--------|------------|----------------|
| Provider | Trusted CA (Let's Encrypt, DigiCert) | Certbot for Let's Encrypt |
| Validation | Domain Validation minimum | Organization Validation preferred |
| Renewal | Auto-renewal before expiry | Cron job or systemd timer |
| Monitoring | Expiry alerts | Prometheus + AlertManager |

### 5.2 Let's Encrypt Setup

```bash
# Install Certbot
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.example.com

# Auto-renewal cron
echo "0 0,12 * * * root python3 -c 'import random; import time; time.sleep(random.random() * 3600)' && certbot renew -q" | sudo tee -a /etc/crontab > /dev/null
```

### 5.3 Certificate Pinning (Optional)

```python
import ssl
import hashlib
import base64

def verify_certificate_pin(cert_der, expected_pins):
    """Verify certificate against pinned public keys"""
    # Calculate SHA256 of public key
    cert = ssl.PEM_cert_to_DER_cert(cert_der)
    public_key = extract_public_key(cert)
    pin = base64.b64encode(hashlib.sha256(public_key).digest()).decode()
    
    return pin in expected_pins

# Configuration
PINNED_CERTIFICATES = [
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',  # Primary cert
    'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB='   # Backup cert
]
```

---

## 6. DEVELOPMENT VS PRODUCTION

### 6.1 Environment Configuration

```python
# config.py
import os

class Config:
    """Base configuration"""
    CORS_ORIGINS = []
    FORCE_HTTPS = False
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:8080']
    FORCE_HTTPS = False
    SSL_DISABLE = True
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    CORS_ORIGINS = ['https://app.example.com']
    FORCE_HTTPS = True
    SSL_DISABLE = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'

# Load config based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}[os.getenv('FLASK_ENV', 'development')]
```

### 6.2 Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.9-slim

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY src/ /app/src/

# SSL certificates volume
VOLUME /etc/ssl/certs

# Production server
CMD ["gunicorn", "--certfile=/etc/ssl/certs/cert.pem", 
     "--keyfile=/etc/ssl/certs/key.pem", 
     "--bind", "0.0.0.0:443", 
     "src.api.app:app"]
```

---

## 7. TESTING & VALIDATION

### 7.1 CORS Testing

```python
# tests/test_cors.py
import pytest
from src.api.app import app

def test_cors_headers():
    client = app.test_client()
    
    # Test preflight
    response = client.options('/face/lock/check',
                             headers={'Origin': 'https://app.example.com'})
    
    assert response.status_code == 200
    assert response.headers['Access-Control-Allow-Origin'] == 'https://app.example.com'
    assert 'POST' in response.headers['Access-Control-Allow-Methods']
    
def test_cors_rejection():
    client = app.test_client()
    
    # Test invalid origin
    response = client.post('/face/lock/check',
                          headers={'Origin': 'https://evil.com'},
                          json={'data': 'test'})
    
    assert 'Access-Control-Allow-Origin' not in response.headers
```

### 7.2 SSL/TLS Testing

```bash
# Test SSL configuration
nmap --script ssl-enum-ciphers -p 443 api.example.com

# Test HSTS
curl -I https://api.example.com | grep Strict-Transport-Security

# SSL Labs test
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=api.example.com

# OpenSSL test
openssl s_client -connect api.example.com:443 -tls1_3
```

---

## 8. MONITORING & ALERTS

### 8.1 Certificate Monitoring

```python
# monitor_certs.py
import ssl
import socket
from datetime import datetime

def check_certificate_expiry(hostname, port=443):
    """Check SSL certificate expiry"""
    context = ssl.create_default_context()
    
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_remaining = (expiry - datetime.now()).days
            
            if days_remaining < 30:
                send_alert(f"Certificate expiring in {days_remaining} days")
            
            return days_remaining
```

### 8.2 CORS Violation Monitoring

```python
@app.errorhandler(403)
def handle_cors_error(e):
    """Log CORS violations for monitoring"""
    logger.warning(f"CORS violation: {request.headers.get('Origin')} -> {request.url}")
    
    # Send to monitoring system
    metrics.increment('cors.violations', tags=['origin:' + request.headers.get('Origin', 'unknown')])
    
    return jsonify({'error': 'CORS policy violation'}), 403
```

---

## 9. COMPLIANCE CHECKLIST

### Development
- [ ] Self-signed certificates for local testing
- [ ] CORS allows localhost origins
- [ ] Security headers present but relaxed
- [ ] HTTPS optional

### Staging
- [ ] Valid SSL certificate from CA
- [ ] CORS restricted to staging domains
- [ ] All security headers enforced
- [ ] HTTPS required

### Production
- [ ] Valid SSL certificate with auto-renewal
- [ ] CORS whitelist strictly enforced
- [ ] All security headers with strict values
- [ ] HSTS preload list submission
- [ ] Certificate monitoring active
- [ ] TLS 1.3 preferred

---

*END OF CORS & HTTPS REQUIREMENTS DOCUMENT*