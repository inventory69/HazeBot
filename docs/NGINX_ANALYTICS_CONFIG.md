# ==================================
# NGINX Config für Analytics Dashboard
# analytics.hzwd.xyz oder als Subdomain
# ==================================

# Add to existing server block or create new one
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name analytics.hzwd.xyz;  # oder test-hazebot-admin.hzwd.xyz/analytics
    
    # SSL Configuration (use existing certs or get new ones)
    ssl_certificate /etc/letsencrypt/live/analytics.hzwd.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/analytics.hzwd.xyz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    
    # Logging
    access_log /var/log/nginx/analytics-access.log;
    error_log /var/log/nginx/analytics-error.log;
    
    # ==================================
    # Basic Auth (Optional - für Sicherheit)
    # ==================================
    auth_basic "Analytics Dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # ==================================
    # Analytics Dashboard
    # ==================================
    location / {
        # Python HTTP Server auf localhost:8082
        proxy_pass http://localhost:8082;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Normal timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}

# HTTP Redirect
server {
    listen 80;
    listen [::]:80;
    
    server_name analytics.hzwd.xyz;
    
    return 301 https://$server_name$request_uri;
}
