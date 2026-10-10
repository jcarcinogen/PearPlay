import importlib.util
from pathlib import Path
import threading
from urllib.request import urlopen
from urllib.error import HTTPError


def test_tv_page_is_static_loopback_only_without_file_serving():
    p = Path(__file__).resolve().parents[1] / 'scripts' / 'tv_test_page.py'
    spec = importlib.util.spec_from_file_location('tv_test_page', p)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.ThreadingHTTPServer(('127.0.0.1', 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = f'http://127.0.0.1:{server.server_port}'
        with urlopen(root + '/', timeout=5) as response:
            assert response.status == 200
            assert response.headers['Cache-Control'] == 'no-store'
            assert response.read() == module.PAGE
        for path in ['/../../etc/passwd', '/index.html?secret=value', '/credentials.json']:
            try:
                urlopen(root + path, timeout=5)
            except HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError('unexpected file route')
        assert b'https://media.w3.org/2010/05/bunny/trailer.mp4' in module.PAGE
        assert b'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8' in module.PAGE
        assert b'fetch(' not in module.PAGE
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
