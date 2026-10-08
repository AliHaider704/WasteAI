# File: deploy/templates/wasteai-headers.conf.tpl
# Installed to /etc/nginx/snippets/wasteai-headers.conf and included in EVERY location of the wasteai block
# (add_header is not inherited once a location defines its own, so each location includes this file).
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Permissions-Policy "camera=(self), microphone=(), geolocation=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
add_header Cross-Origin-Opener-Policy "same-origin" always;
add_header Cross-Origin-Resource-Policy "same-origin" always;
# HSTS: browsers ignore it over plain HTTP (RFC 6797), so it only takes effect on the 443 block. No preload.
add_header Strict-Transport-Security "max-age=31536000" always;
