"""this module define a worker to convert document using unoconv

We abuse a bit unoconv module by monkey patching"""
try:
    import pycurl

    from document_chain.base import BaseWorker

    class HTTPFileSubmitter(BaseWorker):

        name = 'HTTP file submitter'

        def run_action(self, url, file_path, user=None, password=None,
                       field_name='file', **kwargs):
            """Submit file to url

            kwargs may contain optionnal parameters to request
            """
            form = [(field_name, (pycurl.FORM_FILE, file_path))]
            form.extend((k, v) for k, v in kwargs.items() if k != 'next')
            curl = pycurl.Curl()
            curl.setopt(pycurl.URL, url)
            if user is not None:
                curl.setopt(curl.USERPWD, '%s:%s' % (user, password))
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
