"""this module define a worker to convert rml documents to pdf
"""
import os

from document_chain.base import BaseWorker

from z3c.rml import rml2pdf


class RML2PDFWorker(BaseWorker):

    name = 'rml2pdf'

    _converter_cache = None

    def __init__(self, *args, **kwargs):
        BaseWorker.__init__(self, *args, **kwargs)

    def run_action(
        self, src, dest=None, **kwargs):
        """Convert rml at src to pdf at dest using rml2pdf
        """
        if dest is None:
            dest = os.path.splitext(src)[0] + '.pdf'
        rml2pdf.go(src, dest)
