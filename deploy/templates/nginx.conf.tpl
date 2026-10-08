# File: deploy/templates/nginx.conf.tpl
# wasteai-managed server block. install.sh fills the listen and redirect placeholders (port 80, or 443 + Certbot cert files when the
# certificate exists, plus a port 80 -> https redirect). Never edit by hand on the host: edit this file, re-run install.sh.

# Edge rate limit: 10 requests per minute per client address (the app limiter stays as second line).
limit_req_zone $binary_remote_addr zone=wasteai:5m rate=10r/m;
limit_req_zone $binary_remote_addr zone=wasteai_fb:2m rate=6r/m;
limit_req_zone $binary_remote_addr zone=wasteai_log:2m rate=20r/m;
limit_conn_zone $binary_remote_addr zone=wasteai_conn:5m;

# Localized messages, same wording as contract/errors.json (language from ?lang=ar|en, default en).
map $arg_lang $wasteai_msg_too_large {
    default "Image must be 2 MB or less.";
    ar "يجب ألا يتجاوز حجم الصورة 2 ميغابايت.";
}
map $arg_lang $wasteai_msg_rate {
    default "Too many requests. Please wait a moment and try again.";
    ar "عدد الطلبات كبير جدًا. يرجى الانتظار قليلًا ثم المحاولة مرة أخرى.";
}

server {
    __LISTEN__
    server_name __DOMAIN__;

    root __APP__/frontend;
    index index.html;
    client_max_body_size 3m;
    server_tokens off;
    client_header_timeout 10s;
    client_body_timeout 10s;
    send_timeout 15s;
    limit_conn wasteai_conn 20;

    error_page 413 = @too_large;

    location /api/ {
        include /etc/nginx/snippets/wasteai-headers.conf;
        # The app sets the same headers for non-Nginx use; hide them so each is sent once.
        proxy_hide_header Content-Security-Policy;
        proxy_hide_header X-Content-Type-Options;
        proxy_hide_header Referrer-Policy;
        proxy_hide_header Permissions-Policy;
        proxy_hide_header Cross-Origin-Opener-Policy;
        proxy_hide_header Cross-Origin-Resource-Policy;
        proxy_hide_header Strict-Transport-Security;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 15s;
        proxy_pass http://127.0.0.1:__PORT__;

        location = /api/v1/classify {
            limit_req zone=wasteai burst=3 nodelay;
            limit_req_status 429;
            error_page 429 = @rate_limited;
            proxy_pass http://127.0.0.1:__PORT__;
        }

        location = /api/v1/feedback {
            limit_req zone=wasteai_fb burst=3 nodelay;
            limit_req_status 429;
            error_page 429 = @rate_limited;
            proxy_pass http://127.0.0.1:__PORT__;
        }

        location = /api/v1/log {
            limit_req zone=wasteai_log burst=10 nodelay;
            limit_req_status 429;
            error_page 429 = @rate_limited;
            proxy_pass http://127.0.0.1:__PORT__;
        }
    }

    location @too_large {
        internal;
        include /etc/nginx/snippets/wasteai-headers.conf;
        default_type "application/json; charset=utf-8";
        return 413 '{"error":{"code":"image_too_large","message":"$wasteai_msg_too_large","request_id":"$request_id"}}';
    }

    location @rate_limited {
        internal;
        include /etc/nginx/snippets/wasteai-headers.conf;
        add_header Retry-After "6" always;
        default_type "application/json; charset=utf-8";
        return 429 '{"error":{"code":"rate_limited","message":"$wasteai_msg_rate","request_id":"$request_id"}}';
    }

    # Fonts are versioned by folder and never change in place: long cache. Everything else revalidates.
    location ^~ /assets/fonts/ {
        include /etc/nginx/snippets/wasteai-headers.conf;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        access_log off;
    }

    location ~* \.svg$ {
        include /etc/nginx/snippets/wasteai-headers.conf;
        add_header Cache-Control "no-cache" always;
        access_log off;
    }

    location / {
        include /etc/nginx/snippets/wasteai-headers.conf;
        add_header Cache-Control "no-cache" always;
        try_files $uri $uri/ /index.html;
    }
}
__REDIRECT__
