"""Renderer service: ``python -m app.renderer``.

Internal-only HTTP endpoint the screening worker calls when a fetched
page is a JavaScript shell. Holds no secrets and no database access, so a
compromised browser process gains nothing but outbound web fetches — which
are themselves SSRF-filtered (see app.services.render).

POST /render  {"url": "..."}  ->  200 {"final_url", "status", "html"}
                              ->  422 {"error": kind, "detail": ...}
GET  /health                  ->  200 {"ok": true}
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from os import environ

from app.services.fetch import FetchError
from app.services.render import RenderError, render

logger = logging.getLogger(__name__)
MAX_REQUEST_BYTES = 8192
_slots = threading.BoundedSemaphore(int(environ.get('RENDER_CONCURRENCY', '2')))


class Handler(BaseHTTPRequestHandler):
    server_version = 'jp-renderer'

    def _reply(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == '/health':
            self._reply(200, {'ok': True})
        else:
            self._reply(404, {'error': 'not_found'})

    def do_POST(self) -> None:
        if self.path != '/render':
            self._reply(404, {'error': 'not_found'})
            return
        length = int(self.headers.get('Content-Length') or 0)
        if not 0 < length <= MAX_REQUEST_BYTES:
            self._reply(413, {'error': 'bad_request'})
            return
        try:
            url = json.loads(self.rfile.read(length))['url']
            if not isinstance(url, str):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            self._reply(400, {'error': 'bad_request'})
            return
        if not _slots.acquire(timeout=30):
            self._reply(503, {'error': 'busy'})
            return
        try:
            result = render(url)
        except (FetchError, RenderError) as exc:
            logger.info('render %s failed: %s', url, exc.kind)
            self._reply(422, {'error': exc.kind, 'detail': exc.detail[:300]})
            return
        except Exception:
            logger.exception('render %s crashed', url)
            self._reply(500, {'error': 'render_failed'})
            return
        finally:
            _slots.release()
        logger.info('rendered %s (%d bytes)', url, len(result.content))
        self._reply(200, {'final_url': result.final_url,
            'status': result.status, 'html': result.content.decode('utf-8')})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    port = int(environ.get('RENDERER_PORT', '9000'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    logger.info('renderer listening on :%d', port)
    server.serve_forever()


if __name__ == '__main__':
    main()
