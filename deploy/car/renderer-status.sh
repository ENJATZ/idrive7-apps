#!/bin/sh
set -u

echo 'Renderer services'
for unit in idrive7-renderd.service mgu-renderd.service mgu-render.service; do
    if command -v systemctl >/dev/null 2>&1; then
        state=$(systemctl is-active "$unit" 2>/dev/null || true)
        echo "  $unit: ${state:-unknown}"
    fi
done

echo 'Renderer sockets'
for socket in /run/mgu-renderd/renderd.sock /run/mgu-render/render.sock; do
    if [ -S "$socket" ]; then
        ls -l "$socket"
    else
        echo "  $socket: absent"
    fi
done

echo 'Graphics implementation and recent renderer statistics'
if command -v journalctl >/dev/null 2>&1; then
    journalctl --no-pager -b -n 300 -u idrive7-renderd.service -u mgu-renderd.service -u mgu-render.service 2>/dev/null |
        grep -E 'GL:|stats .*m_drive|path layer|error|failed' | tail -n 30 || true
else
    echo '  journalctl is unavailable'
fi

echo 'Open M Drive with Renderer set to Automatic. GPU in the header identifies the native renderer path.'
echo 'Check the GL line for the actual graphics driver. A socket alone does not establish hardware acceleration.'
echo 'An idle screen sends about one keepalive frame per second; measure FPS with changing RPM or boost.'
