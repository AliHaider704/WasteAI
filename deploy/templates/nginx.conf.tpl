# deploy/templates/nginx.conf.tpl
# Own server block for wasteai. Certbot (--nginx) adds the 443/SSL parts later.
server {
    listen 80;
    listen [::]:80;
    server_name __DOMAIN__;

    root __APP__/frontend;
    index index.html;
    client_max_body_size 3m;

    location /api/ {
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 15s;
    }

    location / {
        try_files $uri $uri/ /index.html;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "no-referrer" always;
        add_header Permissions-Policy "camera=(self), microphone=()" always;
        add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'" always;
    }

    location ~* \.(woff2|svg)$ {
        expires 30d;
        access_log off;
    }
}
