"""
This module provides a simple wsgi app that will help a user to
get a file resulting from a document_chain process.
It is designed to be used in an iframe.

It will display a wait message until the task file appears in a certain
directory. It may also display a failure message if the task ends in a error
directory.

As soon as the task is found, the result file is sent to the user.
"""
import mimetypes
import os
import shutil
import urlparse

from ConfigParser import SafeConfigParser


CHUNK_SIZE = 2**16


def remove_all(dirs):
    if dirs:
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)


def any(iterator):
    for i in iterator:
        if i:
            return True
    return False


class WSGIWaitTask(object):
    """WSGI application that will wait for a task to finish and serve a file
    afterwards (usually the result of the task).

    other parameters are in the request, see __call__
    """

    def __init__(self, base_path='/', use_http_refresh=True):
        self.base_path = base_path
        self.use_http_refresh = use_http_refresh

    def __call__(self, environ, start_response):
        """
        request is a GET,
        a single argument must be passed in request : id,
        this id correpond to a file in app base_path.

        This file is a  .ini,
        which contains parameters :

        done_path
          path where the task should be found when done
        result_path
          path of the file to send when task is done
        wait_page (optional)
          path of a file which content will be diplayed while waiting
        err_page (optional)
          path of a file which content will be diplayed if an error occured
        poll_time (optional)
          time between two checks
        err_path (optional)
          path where the task should be found
          if processing went wrong (it may be a comma separated list of path)
        result_name (optional)
          which name to give to result file
        result_type (optional)
          which content_type to give to result file
        remove_dirs (optional)
          path of dirs that must be removed after result file has been sent
          (it may be a comma separated list of path)
        
        """
        form = urlparse.parse_qs(environ['QUERY_STRING'])
        id_ = form.get('id')[0]
        config = None
        if id_:
            config = SafeConfigParser()
            parsed = config.read(os.path.join(self.base_path, id_ + '.ini'))
            if not parsed:
                config = None

        if config is None:
            # error
            return self.send_error(
                start_response, msg='Error : Unknown id %s' % id_)

        form = dict(config.items('main'))

        done_path = form.get('done_path', '').strip()
        err_path = [p.strip()
            for p in form.get('err_path', '').split(',')]
        result_path = form.get('result_path', '').strip()

        if os.path.exists(done_path):
            # yeah send result file as attachment if it exists
            remove_dirs = [p.strip()
                for p in form.get('remove_dirs', '').split(',')]
            content_type = form.get(
                'result_type',
                mimetypes.guess_type(result_path)[0] or
                    'application/octet-stream')
            name = form.get('result_name', os.path.basename(result_path))
            return SendFileIterator(
                result_path,
                content_type=content_type,
                name=name,
                start_response=start_response,
                on_close=lambda: remove_all(remove_dirs))
        elif any(os.path.exists(p) for p in err_path):
            return self.send_error(
                start_response, form.get('err_page', '').strip())
        else:
            # wait page
            return self.wait_page(
                start_response,
                wait_page=form.get('wait_page'),
                poll_time=max(int(form.get('poll_time', 10)), 3))

    def send_error(self,
                   start_response,
                   err_page=None,
                   msg='Error: processing failed'):
        if err_page:
            content = open(err_page).read()
            ctype = mimetypes.guess_type(err_page)[0] or 'text/html'
        else:
            content = msg
            ctype = 'text/plain'
        start_response(
            '500 Server Error',
            [('Content-Type', ctype), ('Content-Length', len(content))])
        return content

    def wait_page(self, start_response, wait_page, poll_time):
        headers = {'Content-Type': 'text/html'}
        if wait_page:
            content = open(wait_page).read()
            headers['Content-Type'] = (
                mimetypes.guess_type(wait_page)[0] or 'text/html')
        else:
            content = 'Please wait'
            headers['Content-Type'] = 'text/plain'
        headers['Content-Length'] = len(content)
        if self.use_http_refresh and poll_time:
            headers['Refresh'] = str(poll_time)
        start_response(
            '200 OK',
            headers.items())
        return content

    @classmethod
    def app_factory(
            cls, global_config, base_path='/', use_http_refresh='true'):
        use_http_refresh = use_http_refresh.lower != 'false'
        return cls(base_path, use_http_refresh)


class SendFileIterator(object):

    def __init__(self, path, content_type, name, start_response, on_close=None):
        self.path = path
        self.content_type = content_type
        self.name = name
        self.start_response = start_response
        self.on_close = on_close

    def __iter__(self):
        path = self.path
        if os.path.exists(path):
            headers = {
                'Content-Type': self.content_type,
                'Content-Length': os.stat(path).st_size,
                'Content-Disposition':
                    'attachement; filename=%s' % self.name}
            self.start_response('200 OK', headers.items())
            with open(path) as f:
                data = f.read(CHUNK_SIZE)
                while data:
                    yield data
                    data = f.read(CHUNK_SIZE)
        else:
            # empty response
            headers = {'Content-Type': 'text/plain'}
            self.start_response('500 Internal Server Error', headers.items())
            yield "Can't retrieve file"

    def close(self):
        self.on_close()
