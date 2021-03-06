"""utility to run a worker, based on a config file parameters"""
from ConfigParser import SafeConfigParser
import grp
try:
    import importlib
except ImportError:
    import _importlib as importlib
from optparse import OptionParser
import os
import pwd
import signal
import sys

import daemon
from daemon.runner import make_pidlockfile, DaemonRunner

from document_chain.http_submitter import HTTPFileSubmitter
from document_chain.unoconv_worker import UnoConvWorker
try:
    from document_chain.rml2pdf_worker import RML2PDFWorker
except ImportError:
    pass


parser = OptionParser(usage="%prog [options] worker")
parser.add_option("-c", "--config",
                  help="use config file (default is config.ini)",
                  default='config.ini', dest="filename")
parser.add_option("-s", "--section",
                  help="Use section of config file (default is main)",
                  default='main', dest="section")
parser.add_option("--no-detach",
                  help="Do not detach (useful for debugging)",
                  action="store_false", dest="detach", default=True)
parser.add_option("-p", "--pid-file",
                  help="Use this file for pid (default in <worker name>.pid)",
                  default=None, dest="pid")
parser.add_option("-l", "--log-file",
                  help="Use this file for log (default in <worker name>.log)",
                  default=None, dest="log")
parser.add_option("-w", "--work-dir",
                  help="set working dir (default si /)",
                  default=None, dest="wdir")
parser.add_option("-u", "--user",
                  help="set user running daemon",
                  default=None, dest="user")
parser.add_option("-g", "--group",
                  help="set group of running daemon",
                  default=None, dest="grp")


def load_class(fullname):
    module, class_name = fullname.rsplit('.', 1)
    if module not in sys.modules:
        importlib.import_module(module)
    return getattr(sys.modules[module], class_name)


def worker_from_config(worker_name, filename, section='main'):
    config_parser = SafeConfigParser()
    config_parser.read(filename)
    prefix = worker_name + '_'
    config = dict((k[len(prefix):], v)
                    for k, v in config_parser.items(section)
                    if k.startswith(prefix))
    klass_name = config_parser.get(section, worker_name)
    # if dotted name load, else takes from globals
    if '.' in klass_name:
        klass = load_class(klass_name)
    else:
        klass = globals()[klass_name]
    worker = klass(**config)
    worker.name = worker_name
    return worker


def term_handler(daemon):
    def handler(signum, frame):
        import sys
        print >>sys.stderr, "handling term"
        daemon.app.worker.stop()
        print >>sys.stderr, "worker stoped"
        daemon.daemon_context.terminate(signum, frame)
    return handler


class App(object):

    def __init__(self, worker):
        self.worker = worker

    def run(self):
        self.worker.start()


class WorkerDaemon(DaemonRunner):

    def __init__(self, parser=parser, argv=None):
        # daemon use old __stdin__ semantic while multiprocessing eg. may not
        # care about it and close stdin without replacing __stdin__
        sys.__stdin__ = sys.stdin

        self.parser = parser
        self.parse_args(argv)
        context_args = {}
        if not self.detach_process:
            context_args['stdin'] = sys.stdin
            context_args['stdout'] = sys.stdout
            context_args['stderr'] = sys.stderr
        dc = self.daemon_context = daemon.DaemonContext(
            umask = 0o007,
            working_directory=self.wdir,
            detach_process = self.detach_process,
            **context_args)
        owner = [-1, -1]
        if self.uid is not None:
            owner[0] = self.uid
        if self.gid is not None:
            owner[1] = self.gid
        if self.detach_process:
            log = open(self.log_path, 'a+', buffering=0)
            os.chown(self.log_path, *owner)
            dc.stderr = log
        self.pidfile = dc.pidfile = make_pidlockfile(self.pid_path, 5000)
        if self.uid is not None:
            dc.uid = self.uid 
        if self.gid is not None:
            dc.gid = self.gid 
        handler = term_handler(self)
        dc.signal_map[signal.SIGTERM] = handler
        if not self.detach_process:
            dc.signal_map[signal.SIGINT] = handler

    def parse_args(self, argv=None):
        if argv is None:
            options, args = parser.parse_args()
        else:
            options, args = parser.parse_args(argv)
        self.action = args.pop()
        worker_name = args.pop()
        if args:
            raise Exception('too much args')
        self.app = App(worker_from_config(worker_name, options.filename,
                                        options.section))
        self.pid_path = options.pid or worker_name + '.pid'
        if not self.pid_path == os.path.abspath(self.pid_path):
            self.pid_path = os.path.join(options.wdir or os.getcwd(),
                                         self.pid_path)
        self.log_path = options.log or worker_name + '.log'
        if not self.log_path == os.path.abspath(self.log_path):
            self.log_path = os.path.join(options.wdir or os.getcwd(),
                                         self.log_path)
        self.wdir = options.wdir
        if options.user:
            self.uid = pwd.getpwnam(options.user).pw_uid
        else:
            self.uid = None
        if options.grp:
            self.gid = grp.getgrnam(options.grp).gr_gid
        else:
            self.gid = None
        self.detach_process = options.detach


def main(argv=None):
    WorkerDaemon(parser, argv).do_action()

    
if __name__ == '__main__':
    main()
