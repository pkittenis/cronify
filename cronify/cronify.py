import os
import pyinotify
import time
import fnmatch
import logging
import sys
import threadpool
import subprocess
import pytz

_MASKS = pyinotify.IN_CLOSE_WRITE | pyinotify.IN_MOVED_FROM

logger = logging.getLogger(__name__)

def _setup_logger(_logger):
    """Setup default logger"""
    tp_logger = logging.getLogger('threadpool')
    _handler = logging.StreamHandler()
    log_format = logging.Formatter('%(name)s - %(threadName)s - %(asctime)s - %(levelname)s - %(message)s')
    _handler.setFormatter(log_format)
    _logger.addHandler(_handler)
    tp_logger.addHandler(_handler)
    _logger.setLevel(logging.DEBUG)
    tp_logger.setLevel(logging.DEBUG)

def run_script(cmd_args):
    """Run cmd line script
    :type: list
    :param cmd_args: List of cmd and arguments to run, eg ['ls', '-l']
    :rtype: tuple
    :returns: returncode, stdout, stderr"""
    p = subprocess.Popen(cmd_args, shell = False, stdout = subprocess.PIPE)
    stdout, stderr = p.communicate()
    return p.returncode, stdout, stderr

class EventHandler(pyinotify.ProcessEvent):
    _filename_keyword = '$filename'
    def __init__(self, filemask, actions, tp):
        self.filemask, self.actions, self.tp = filemask, actions, tp

    def process_IN_CREATE(self, event):
        self.handle_event(event)
    def process_IN_DELETE(self, event):
        self.handle_event(event)
    def process_IN_CLOSE_WRITE(self, event):
        self.handle_event(event)
    def process_IN_CLOSE_NOWRITE(self, event):
        self.handle_event(event)
    def process_IN_MOVED_FROM(self, event):
        self.handle_event(event)

    def handle_event(self, event):
        """Check triggered event against filemask, do actions if filemask is accepted"""
        if not fnmatch.fnmatch(event.name, self.filemask):
            return
        logger.debug("Matched filename %s with filemask %s from event %s" % (event.name, self.filemask, event.maskname,))
        self.do_actions(event)

    def _parse_action_args(self, event, action_args):
        """Parse action_args, return args with expanded keywords"""
        for i in range(len(action_args)):
            arg = action_args[i]
            arg.strip()
            if arg == self._filename_keyword:
                action_args[i] = event.name
        return action_args

    def do_actions(self, event):
        """Perform actions"""
        logger.debug("Starting actions %s" % (self.actions,))
        for action in self.actions:
            for action_name, action_data in action.iteritems():
                action_args = self._parse_action_args(event, action_data['args'])
                logger.debug("Made expanded action arguments %s" % (action_args,))
                action_args.insert(0, action_data['cmd'])
                self.tp.add_task_to_queue(run_script, action_args)
                logger.info("Got result from action %s - %s" % (action_data, self.tp.get_results([action]),))

class Watcher(object):
    _req_data_fields = [ 'directory', 'filemask', 'actions' ]

    def __init__(self, watch_data):
        self.watch_manager = pyinotify.WatchManager()
        self.wdds, self.notifiers = [], []
        if not self._check_watch_data_fields(watch_data):
            sys.exit(1)
        self.watch_data = watch_data
        self.tp = threadpool.ThreadPool(num_workers = 10)
        self.start_watchers(watch_data)

    def _check_watch_data_fields(self, watch_data):
        """Check for required watch data fields
        :type: dict
        :param watch_data: Watch data
        :rtype: bool"""
        for watch in watch_data:
            if not [True for field in self._req_data_fields if field in watch_data[watch]] == [True for field in self._req_data_fields]:
                logger.critical("Watch configuration for %s is missing required fields from %s. Data is %s" %
                                (watch, self._req_data_fields, watch_data[watch],))
                return False
        return True

    def start_watchers(self, watch_data):
        """Go through watch_data and start watchers"""
        for watcher in watch_data:
            watch_dir = self._check_dir(watch_data[watcher]['directory'])
            if not watch_dir:
                logger.critical("Desired directory to watch %s does not exist or is not a directory. Exiting." % (watch_dir,))
                sys.exit(1)
            recurse = watch_data[watcher]['recurse']
            notifier = pyinotify.ThreadedNotifier(self.watch_manager, EventHandler(watch_data[watcher]['filemask'],
                                                                                   watch_data[watcher]['actions'],
                                                                                   self.tp))
            notifier.start()
            self.notifiers.append(notifier)
            self.wdds.append(self.watch_manager.add_watch(watch_dir, _MASKS, rec = recurse))

    def _check_dir(self, dirpath):
        """Make absolute path, check is directory"""
        dirpath = os.path.abspath(dirpath)
        if not os.path.isdir(dirpath):
            return
        return dirpath

    def cleanup(self):
        """Stop watchers, shutdown notifiers"""
        [self.watch_manager.rm_watch(wdd.values()) for wdd in self.wdds]
        [notifier.stop() for notifier in self.notifiers]

def test():
    watch_data = {'access_log_watcher':
                  {'directory': '/tmp/testdir',
                   'filemask': 'somefile.txt',
                   'recurse': False,
                   'actions': [
                       { 'checkFile': {'cmd': 'echo', 'args': ['$filename', 'YYYYMMDD']}},]
                   }}
    # {'processFile': {'cmd': 'process', 'args': ['$filename', 'YYYYMMDD']}}

    watcher = Watcher(watch_data)
    while True:
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            watcher.cleanup()
            sys.exit(0)

if __name__ == "__main__":
    _setup_logger(logger)
    test()
