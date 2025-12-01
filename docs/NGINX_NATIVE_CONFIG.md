# NGINX Configuration for HazeBot Admin Panel
## Native nginx Setup (non-SWAG)

---

## File Location

- **Ubuntu/Debian**: `/etc/nginx/sites-available/hazebot-admin.conf`
- **CentOS/RHEL**: `/etc/nginx/conf.d/hazebot-admin.conf`

---

## Installation Steps

### 1. Install nginx and certbot
```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

### 2. Create configuration file
```bash
sudo nano /etc/nginx/sites-available/hazebot-admin.conf
```

### 3. Paste the configuration below

### 4. Enable site (Ubuntu/Debian only)
```bash
sudo ln -s /etc/nginx/sites-available/hazebot-admin.conf /etc/nginx/sites-enabled/
```

### 5. Test configuration
```bash
sudo nginx -t
```

### 6. Reload nginx
```bash
sudo systemctl reload nginx
```

### 7. Get SSL certificate
```bash
sudo certbot --nginx -d test-hazebot-admin.hzwd.xyz
```

---

## Main Configuration File

```nginx
# ==================================
# NGINX Config für test-hazebot-admin.hzwd.xyz
# Native nginx Setup (non-SWAG)
# ==================================

# WebSocket Upgrade Map
# Add this to /etc/nginx/nginx.conf in the http { } block if not already present
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

# ==================================
# HTTP Server Block (Port 80)
# Redirects to HTTPS
# ==================================
server {
    listen 80;
    listen [::]:80;
    
    server_name test-hazebot-admin.hzwd.xyz;
    
    # Allow Certbot ACME challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    # Redirect all other HTTP traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# ==================================
# HTTPS Server Block (Port 443)
# Main application server
# ==================================
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name test-hazebot-admin.hzwd.xyz;
    
    # ==================================
    # SSL Configuration
    # ==================================
    # Managed by Certbot - these will be added automatically after running certbot
    # ssl_certificate /etc/letsencrypt/live/test-hazebot-admin.hzwd.xyz/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/test-hazebot-admin.hzwd.xyz/privkey.pem;
    # include /etc/letsencrypt/options-ssl-nginx.conf;
    # ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    
    # Strong SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # ==================================
    # Client Settings
    # ==================================
    client_max_body_size 10M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    
    # ==================================
    # Logging
    # ==================================
    access_log /var/log/nginx/hazebot-admin-access.log;
    error_log /var/log/nginx/hazebot-admin-error.log warn;
    
    # ==================================
    # Security Headers
    # ==================================
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # ==================================
    # WebSocket (Socket.IO)
    # ==================================
    location /socket.io/ {
        # Flask Backend on 192.168.0.188:5070
        proxy_pass http://192.168.0.188:5070/socket.io/;
        
        # Proxy Headers
        proxy_pass_request_headers on;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket Support - CRITICAL for Socket.IO
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        
        # Long timeouts for persistent WebSocket connections
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
        
        # Disable buffering for real-time communication
        proxy_buffering off;
        proxy_cache off;
    }
    
    # ==================================
    # API Backend (Flask)
    # ==================================
    location /api/ {
        # Flask Backend on 192.168.0.188:5070
        proxy_pass http://192.168.0.188:5070;
        
        # Proxy Headers - IMPORTANT for Authorization tokens
        proxy_pass_request_headers on;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # Extended timeouts for API requests
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # WebSocket Support (for potential upgrades)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        
        # Disable buffering for faster responses
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # ==================================
    # Frontend (Flutter Web SPA)
    # ==================================
    location / {
        # Flutter SPA on 192.168.0.188:8080
        proxy_pass http://192.168.0.188:8080;
        
        # Proxy Headers
        proxy_pass_request_headers on;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Normal timeouts for SPA
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # WebSocket Support (for hot reload in dev)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
}
```

---

## Alternative: Serve Static Flutter Build

If you want nginx to serve the Flutter build directly instead of proxying:

### Configuration

Replace the `location / { }` block with:

```nginx
location / {
    root /var/www/hazebot-admin;
    try_files $uri $uri/ /index.html;
    
    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # No cache for index.html (SPA entry point)
    location = /index.html {
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
    }
}
```

### Setup Steps

1. **Build Flutter web**:
```bash
cd /home/liq/gitProjects/HazeBot-Admin
flutter build web --release --pwa-strategy=none
```

2. **Copy build to nginx root**:
```bash
sudo mkdir -p /var/www/hazebot-admin
sudo cp -r build/web/* /var/www/hazebot-admin/
sudo chown -R www-data:www-data /var/www/hazebot-admin
sudo chmod -R 755 /var/www/hazebot-admin
```

3. **Reload nginx**:
```bash
sudo systemctl reload nginx
```

---

## Testing

### Test nginx syntax
```bash
sudo nginx -t
```

### Check listening ports
```bash
sudo netstat -tlnp | grep nginx
```

### Test endpoints
```bash
# HTTP redirect
curl -I http://test-hazebot-admin.hzwd.xyz

# API health check
curl -I https://test-hazebot-admin.hzwd.xyz/api/health

# WebSocket (should return 400 without upgrade header)
curl -I https://test-hazebot-admin.hzwd.xyz/socket.io/
```

### Test WebSocket with wscat
```bash
# Install wscat
npm install -g wscat

# Test connection
wscat -c wss://test-hazebot-admin.hzwd.xyz/socket.io/?EIO=4&transport=websocket
```

---

## Firewall Configuration

### UFW (Ubuntu/Debian)
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

### firewalld (CentOS/RHEL)
```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## Troubleshooting

### Check nginx error log
```bash
sudo tail -f /var/log/nginx/hazebot-admin-error.log
```

### Check backend connectivity
```bash
curl http://192.168.0.188:5070/api/health
```

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| 502 Bad Gateway | Backend not running | Start Flask/Flutter backend |
| 504 Gateway Timeout | Backend too slow | Check backend logs, increase timeouts |
| WebSocket failed | Missing headers | Check WebSocket map in nginx.conf |
| SSL errors | Certificate issues | Run `sudo certbot --nginx` again |

---

## Monitoring (Optional)

### Enable nginx status page

Add to server block:

```nginx
location /nginx_status {
    stub_status on;
    access_log off;
    allow 127.0.0.1;
    allow 192.168.0.0/24;  # Your local network
    deny all;
}
```

### Check status
```bash
curl http://localhost/nginx_status
```

---

## Differences from SWAG

| Feature | SWAG Config | Native nginx |
|---------|-------------|--------------|
| **SSL Certs** | `/config/nginx/ssl.conf` | `/etc/letsencrypt/` (Certbot) |
| **Logs** | `/config/log/nginx/` | `/var/log/nginx/` |
| **Config Files** | `/config/nginx/proxy-confs/` | `/etc/nginx/sites-available/` |
| **SSL Renewal** | Automatic | Certbot cron job |
| **WebSocket Map** | Included | Add to nginx.conf |
| **Root User** | Container | System nginx user |

---

## Maintenance

### Reload nginx after config changes
```bash
sudo systemctl reload nginx
```

### Restart nginx (if reload doesn't work)
```bash
sudo systemctl restart nginx
```

### Check nginx status
```bash
sudo systemctl status nginx
```

### View all logs
```bash
sudo tail -f /var/log/nginx/*.log
```

### SSL certificate renewal (automatic via cron)
```bash
# Test renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal
```

---

## Performance Tuning (Optional)

Add to `/etc/nginx/nginx.conf` in `http { }` block:

```nginx
# Worker processes (usually = number of CPU cores)
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript 
               application/json application/javascript application/xml+rss 
               application/rss+xml application/atom+xml image/svg+xml 
               text/x-js text/x-component;
    
    # Connection settings
    keepalive_timeout 65;
    keepalive_requests 100;
    
    # Buffer sizes
    client_body_buffer_size 128k;
    client_max_body_size 10m;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 16k;
}
```

