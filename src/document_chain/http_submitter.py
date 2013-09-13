"""this module define a worker to submit http requests

You can

- define the url to request
- define the user and password to use for basic auth
- a submit file thanks to the file_path parameter
  associated to field_name
- add http headers thanks to paramaters beginig with @
- and add as many request parameters
"""


try:
    import pycurl

    from document_chain.base import BaseWorker

    class HTTPFileSubmitter(BaseWorker):

        name = 'HTTP file submitter'

        HEADER_PREFIX = '@'

        def run_action(self, url, file_path=None, user=None, password=None,
                       field_name='file', **kwargs):
            """Submit file to url

            kwargs may contain optionnal parameters to request
            
            if a kwarg key begins with @ it is taken as an http header
            """
            headers = [': '.join((k[1:], v)) for k, v in kwargs.items()
                if k.startswith(self.HEADER_PREFIX)]
            form = []
            if file_path is not None:
                form.append((field_name, (pycurl.FORM_FILE, file_path)))
            form.extend((k, v) for k, v in kwargs.items()
                if k != 'next' and not k.startswith(self.HEADER_PREFIX))
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, url)
            if user is not None:
                curl.setopt(curl.USERPWD, '%s:%s' % (user, password))
            import pdb;pdb.set_trace()
            if headers:
                curl.setopt(pycurl.HTTPHEADER, headers)
            curl.setopt(curl.HTTPPOST, form)
            # FIXME : get output and return code !
            curl.perform()
            code = curl.getinfo(pycurl.HTTP_CODE)
            curl.close()
            if code != 200:
                raise Exception('Unexpected return code from server : %s' %
                                code)

except ImportError:
    pass
