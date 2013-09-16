from __future__ import with_statement

import base64
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import os
import shutil
from StringIO import StringIO
import tempfile
import threading

import pytest

from document_chain.http_submitter import HTTPFileSubmitter


tmpdir = None  # we need to have a global tempdir to remove it after tests
log = StringIO()
headers = None


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        ctx_mgr = self.server.ctx_mgr
        ctx_mgr.headers = self.headers
        ctx_mgr.data = self.rfile.read(int(self.headers['Content-length']))
        if 'authorization' in self.headers:
            auth = base64.decodestring(self.headers['authorization']
                                                   [len('Basic '):])
        else:
            auth = None
        if 'name="do_auth"' in ctx_mgr.data and not auth == 'me:MyPass':
            no, msg = 403, "auth please !"
        elif 'name="do_raise"' in ctx_mgr.data:
            no, msg = 503, "ko"
        else:
            no, msg = 200, 'ok'
        self.send_response(no, msg)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(msg)

    def do_GET(self):
        self.send_response(200, 'OK')
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("ok")


class HTTPServe(object):

    headers = None
    data = None
    status = None
    msg = None

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
    """just test the action is working with additional params"""
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


def test_run_action_503():
    file_path = os.path.join(tmpdir, 'test.txt')
    with open(file_path, 'w') as f:
        f.write("My text !\n")
    worker = HTTPFileSubmitter(tmpdir, tmpdir)
    with HTTPServe() as served:
        with pytest.raises(Exception):
            worker.run_action(url="http://localhost:8888", file_path=file_path,
                                do_raise='yes')


def test_auth():
    file_path = os.path.join(tmpdir, 'test.txt')
    with open(file_path, 'w') as f:
        f.write("My text !\n")
    worker = HTTPFileSubmitter(tmpdir, tmpdir)
    with HTTPServe() as served:
        with pytest.raises(Exception):
            worker.run_action(url="http://localhost:8888", file_path=file_path,
                                do_auth='yes')
    with HTTPServe() as served:
        with pytest.raises(Exception):
            worker.run_action(url="http://localhost:8888", file_path=file_path,
                                user='me', password='NotMyPass', do_auth='yes')
    with HTTPServe() as served:
        worker.run_action(url="http://localhost:8888", file_path=file_path,
                        user='me', password='MyPass', do_auth='yes')

def test_http_headers():
    worker = HTTPFileSubmitter(tmpdir, tmpdir)
    with HTTPServe() as served:
        worker.run_action(url="http://localhost:8888",
                          foo='bar', 
                          **{'@x-my-header': 'foo'})
        assert served.headers['x-my-header'] == 'foo'
