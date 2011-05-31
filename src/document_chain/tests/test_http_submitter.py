from __future__ import with_statement

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import os
import shutil
from StringIO import StringIO
import tempfile
import threading

from document_chain.http_submitter import HTTPFileSubmitter


tmpdir = None  # we need to have a global tempdir to remove it after tests
log = StringIO()
headers = None


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        ctx_mgr = self.server.ctx_mgr
        ctx_mgr.headers = self.headers
        ctx_mgr.data = self.rfile.read(int(self.headers['Content-length']))
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("ok")

    def do_GET(self):
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("ok")


class HTTPServe(object):

    headers = None
    data = None

    def __enter__(self):
        """Launch server in a thread to serve just one request"""
        server_address = ('', 8888)
        httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
        setattr(httpd, 'ctx_mgr', self)
        self.thread = threading.Thread(target=httpd.handle_request)
        self.thread.start()
        return self

    def __exit__(self, *args, **kwargs):
        self.thread.join()


def teardown_function(function):
    if tmpdir and os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)


def setup_function(function):
    global tmpdir  # teardown will remove it
    tmpdir = tempfile.mkdtemp()
    log.truncate(0)
    global headers
    global data
    headers = None
    data = None


def test_run_action():
    """just test the action is working"""
    file_path = os.path.join(tmpdir, 'test.txt')
    with open(file_path, 'w') as f:
        f.write("My text !\n")
    worker = HTTPFileSubmitter(tmpdir, tmpdir)
    with HTTPServe() as served:
        worker.run_action(url="http://localhost:8888", file_path=file_path)
        assert 'filename="test.txt"' in served.data
        assert "My text !\n" in served.data
        assert served.headers['Content-Type'].startswith('multipart/form-data')


def test_run_action_additional_params():
    """just test the action is working"""
    file_path = os.path.join(tmpdir, 'test.txt')
    with open(file_path, 'w') as f:
        f.write("My text !\n")
    worker = HTTPFileSubmitter(tmpdir, tmpdir)
    with HTTPServe() as served:
        worker.run_action(url="http://localhost:8888", file_path=file_path,
                            param1='foo', param2='bar')
        assert 'filename="test.txt"' in served.data
        assert 'name="param1"' in served.data
        assert 'foo' in served.data
        assert 'name="param2"' in served.data
        assert 'bar' in served.data
