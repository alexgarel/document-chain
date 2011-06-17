"""utility to run a worker, based on a config file parameters"""
from ConfigParser import SafeConfigParser
import grp
from optparse import OptionParser
import os
import pwd
import signal

import daemon
from daemon.runner import make_pidlockfile, DaemonRunner


from document_chain.http_submitter import HTTPFileSubmitter
from document_chain.unoconv_worker import UnoConvWorker


parser = OptionParser(usage="%prog [options] worker")
parser.add_option("-c", "--config",
                  help="use config file (default is config.ini)",
                  default='config.ini', dest="filename")
parser.add_option("-s", "--section",
                  help="Use section of config file (default is main)",
                  default='main', dest="section")
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


def worker_from_config(worker_name, filename, section='main'):
    config_parser = SafeConfigParser()
    config_parser.read(filename)
    prefix = worker_name + '_'
    config = dict((k[len(prefix):], v)
                    for k, v in config_parser.items(section)
                    if k.startswith(prefix))
    klass_name = config_parser.get(section, worker_name)
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
        self.parser = parser
        self.parse_args(argv)
        dc = self.daemon_context = daemon.DaemonContext(umask = 0o007,
                                          working_directory=self.wdir)
        log = open(self.log_path, 'a+', buffering=0)
        owner = [-1, -1]
        if self.uid is not None:
            owner[0] = self.uid
        if self.gid is not None:
            owner[1] = self.gid
        os.chown(self.log_path, *owner)
        dc.stderr = log
        self.pidfile = dc.pidfile = make_pidlockfile(self.pid_path, 5000)
        if self.uid is not None:
            dc.uid = self.uid 
        if self.gid is not None:
            dc.gid = self.gid 
        handler = term_handler(self)
        dc.signal_map[signal.SIGTERM] = handler

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

def main(argv=None):
    WorkerDaemon(parser, argv).do_action()
    
if __name__ == '__main__':
    main()
