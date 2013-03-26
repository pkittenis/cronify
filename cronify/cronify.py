import os
import pyinotify
import time
import fnmatch
import logging
import sys
import threadpool
import subprocess
# import pytz
import datetime
import re

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
    _datestamp_re = r'\d{4}\d{2}\d{2}'
    _datestamp_rc = re.compile(_datestamp_re)
    _datestamp_keyword_fmt = ( 'YYYYMMDD', '%Y%m%d' )

    # filemasks_actions = {
    # 'somefile.txt' : [ { 'action1' : { 'cmd' : 'echo', <..> } }, ],
    # 'otherfile.txt' : [ { 'action1' : { 'cmd' : 'cat', <..> } }, ],
    # }
    def __init__(self, filemask_actions, tp, callback_func = None):
        self.filemask_actions, self.tp = filemask_actions, tp
        self.callback_func = callback_func
        for filemask in self.filemask_actions.copy():
            new_filemask = self._parse_filemask(filemask)
            self.filemask_actions[new_filemask] = self.filemask_actions[filemask]
            del self.filemask_actions[filemask]

    def process_IN_CLOSE_WRITE(self, event):
        self.handle_event(event)
    def process_IN_MOVED_FROM(self, event):
        self.handle_event(event)

    def handle_event(self, event):
        """Check triggered event against filemask, do actions if filemask is accepted"""
        for filemask in self.filemask_actions:
            if not filemask.match(event.name):
                logger.debug("Filename %s did not match filemask pattern %s" % (event.name, filemask.pattern,))
                continue
            logger.debug("Matched filename %s with filemask %s from event %s" % (event.name, filemask, event.maskname,))
            self.tp.add_task_to_queue(self.do_actions, event, self.filemask_actions[filemask]['actions'])

    def _parse_action_args(self, event, action_args):
        """Parse action_args, return args with expanded keywords and file metadata
        with data required to perform actions"""
        file_metadata = {}
        for i in range(len(action_args)):
            arg = action_args[i]
            arg.strip()
            if arg == self._filename_keyword:
                action_args[i] = event.pathname
            elif arg == self._datestamp_keyword_fmt[0]:
                file_datestamp = self._parse_datestamp(event.name)
                if not file_datestamp:
                    logger.debug("Could not parse datestamp from filename, falling back to file's modified time")
                    file_datestamp = datetime.date.fromtimestamp(os.stat(event.pathname).st_mtime)
                logger.debug("Parsed datestamp %s for file %s" % (file_datestamp.strftime(self._datestamp_keyword_fmt[1]),
                                                                  event.pathname,))
                action_args[i] = file_datestamp.strftime(self._datestamp_keyword_fmt[1])
                file_metadata['datestamp'] = file_datestamp
        return action_args, file_metadata

    def _parse_action_metadata(self, action):
        """Parse action constraints and return metadata"""
        metadata = {}
        for key in action:
            if key == 'start_time':
                metadata['start_time'] = self._parse_isoformat_time(action[key])
                logger.debug("Parsed action start time %s" % (metadata['start_time'],))
            elif key == 'end_time':
                metadata['end_time'] = self._parse_isoformat_time(action[key])
                logger.debug("Parsed action end time %s" % (metadata['end_time'],))
        return metadata

    def _parse_filemask(self, filemask):
        """Parse filemask constraints like datestamp in filename and return compiled regex for filemask matching"""
        if not self._datestamp_keyword_fmt[0] in filemask:
            return re.compile(fnmatch.translate(filemask))
        return re.compile(filemask.replace(self._datestamp_keyword_fmt[0], self._datestamp_re))

    def _parse_isoformat_time(self, isotime):
        """Parse isotime string into a datetime object
        Accepts ISO format times eg '16:01:00'"""
        (hour, minute, second) = isotime.split(':')
        hour, minute, second = int(hour), int(minute), int(second)
        if (hour < 0 or hour > 24) or (minute < 0 or minute > 60) or (second < 0 or second > 60):
            return
        return datetime.time(hour, minute, second)

    def _parse_datestamp(self, filename):
        """Parse filename for datestamp with self._datestamp_rc regex, return datestamp if valid or None"""
        match = self._datestamp_rc.search(filename)
        if not match:
            return
        try:
            file_datestamp = datetime.datetime.strptime(match.group(), self._datestamp_keyword_fmt[1])
        except ValueError:
            return
        else:
            logger.debug("Parsed file datestamp from date in filename - %s from %s" % (file_datestamp, filename,))
        return datetime.date(file_datestamp.year, file_datestamp.month, file_datestamp.day)

    def do_actions(self, event, actions):
        """Perform actions"""
        logger.debug("Starting actions %s" % (actions,))
        [self._do_action(event, action, action_data) for action in actions
         for action_data in action.itervalues()]

    def _do_action(self, event, action, action_data):
        """Perform a single action"""
        action_metadata = self._parse_action_metadata(action_data)
        action_args, file_metadata = self._parse_action_args(event, action_data['args'])
        logger.debug("Made expanded action arguments %s" % (action_args,))
        action_args.insert(0, action_data['cmd'])
        if action_metadata and 'start_time' in action_metadata and 'end_time' in action_metadata:
            now = datetime.datetime.now()
            start_time = datetime.datetime(file_metadata['datestamp'].year, file_metadata['datestamp'].month,
                                           file_metadata['datestamp'].day, action_metadata['start_time'].hour,
                                           action_metadata['start_time'].minute, action_metadata['start_time'].second)
            if now < start_time:
                logger.info("Action start time %s is in the future, waiting for %s hh:mm:SS" % (start_time, start_time - now,))
                time.sleep((start_time - now).seconds)
            elif now > start_time:
                logger.info("Action start time %s is in the past, not triggering action" % (start_time,))
                return
        if self.callback_func:
            self.callback_func(event)
        returncode, stdout, stderr = run_script(action_args)
        logger.info("Got result from action %s - %s" % (action_data, stdout,))
        if returncode:
            logger.error("Action %s failed with exit code %s, stderr %s" % (action, returncode, stderr,))

class Watcher(object):

    """Watcher class to watch a directory and trigger actions"""

    _req_data_fields = [ 'name', 'filemasks' ]
    _req_filemask_fields = [ 'actions' ]
    _req_action_fields = [ 'cmd', 'args' ]
    _req_time_fields = ['start_time', 'end_time']

    def __init__(self, watch_data, callback_func = None):
        """Start a watcher with watch_data
        :type: dict
        :param watch_data: Dictionary with watch data to use. Eg
        watch_data = {'/tmp/testdir': {'name': 'Some file',
        'filemasks': { 'somefile.txt' : {
        'actions': [ { 'echoFile': { 'cmd' : 'echo', 'args' : [ '$filename', 'YYYYMMDD' ] } } ] } } } }
        Can have multiple directories to watch as well as multiple filemasks per directory and multiple actions per filemask
        :type: function reference
        :param callback_func: Optional callback function to be called when an action is triggered.
        There should be only one positional parameter in callback_func for the event object to be passed in
        """
        self.watch_managers, self.notifiers = [], []
        self.callback_func = callback_func
        if not self._check_data_fields(watch_data, self._req_data_fields):
            sys.exit(1)
        try:
            [sys.exit(1) for watch in watch_data
             if not self._check_data_fields(watch_data[watch]['filemasks'], self._req_filemask_fields)]
            [sys.exit(1) for watch in watch_data for filemask in watch_data[watch]['filemasks']
             if not watch_data[watch]['filemasks'][filemask]['actions']]
            [sys.exit(1) for watch in watch_data for filemask in watch_data[watch]['filemasks']
             for action in watch_data[watch]['filemasks'][filemask]['actions']
             if not self._check_data_fields(action, self._req_action_fields)]
            [sys.exit(1) for watch in watch_data for filemask in watch_data[watch]['filemasks']
             for action in watch_data[watch]['filemasks'][filemask]['actions']
             if (self._req_time_fields[0] in action.values()[0] or self._req_time_fields[1] in action.values()[0])
             and not self._check_data_fields(action, self._req_time_fields)]
        except TypeError:
            logger.critical("Missing required configuration, exiting")
            sys.exit(1)
        self.watch_data = watch_data
        self.tp = threadpool.ThreadPool(num_workers = 10)
        self.start_watchers(watch_data)

    def _check_data_fields(self, data, req_fields):
        """Check for required data fields
        :type: dict
        :param data: Dictionary containing data to check
        :type: list
        :param req_fields: List of required fields that are required in data dictionary
        :rtype: bool
        :returns: False if any required fields are missing
        :returns: True if all required fields are present"""
        if not data:
            logger.critical("Configuration data for %s is empty, cannot continue" % (req_fields,))
            return False
        for _key in data:
            if not [True for field in req_fields if field in data[_key]] == [True for field in req_fields]:
                logger.critical("Configuration data for %s is missing required fields from %s. Data is %s" %
                                (_key, req_fields, data[_key],))
                return False
        return True

    def start_watchers(self, watch_data):
        """Go through watch_data and start watchers"""
        for watcher in watch_data:
            watch_dir = self._check_dir(watcher)
            if not watch_dir:
                logger.critical("Desired directory to watch %s does not exist or is not a directory. Exiting." % (watch_dir,))
                sys.exit(1)
            recurse = watch_data[watcher]['recurse'] if 'recurse' in watch_data[watcher] else False
            watch_manager = pyinotify.WatchManager()
            notifier = pyinotify.ThreadedNotifier(watch_manager, EventHandler(watch_data[watcher]['filemasks'].copy(),
                                                                              self.tp,
                                                                              callback_func = self.callback_func))
            notifier.daemon = True
            notifier.start()
            watch_manager.add_watch(watch_dir, _MASKS, rec = recurse, auto_add = True)
            logger.info("Started watching directory %s with filemasks and actions %s, recurse %s.." %
                        (watch_dir,
                         watch_data[watcher]['filemasks'],
                         recurse,))
            self.notifiers.append(notifier)
            self.watch_managers.append(watch_manager)

    def _check_dir(self, dirpath):
        """Make absolute path, check is directory"""
        dirpath = os.path.abspath(dirpath)
        if not os.path.isdir(dirpath):
            return
        return dirpath

    def cleanup(self):
        """Stop watchers, shutdown notifiers"""
        logger.info("Got cleanup signal, shutting down notifiers..")
        [wm.rm_watch(wm.watches.keys()) for wm in self.watch_managers]
        [notifier.stop() for notifier in self.notifiers]

def callback_func(event):
    print "Got event for %s" % (event.name,)

def test():
    """Run with some test watch data when executed as a script"""
    watch_data = {'/tmp/testdir': {'name': 'Some file',
                                   'filemasks': {
                'somefile_YYYYMMDD.*' : {
                    'actions': [
                        { 'checkFile': {
                                'cmd': 'echo',
                                # 'when' : 'today',
                                # 'days' : '1-5',
                                # 'start_time' : '20:00:00',
                                # 'end_time' : '21:00:00',
                                'args': ['$filename', 'YYYYMMDD']}},]
                    },
                'otherfile_YYYYMMDD.txt' : {
                    'actions': [
                        { 'checkFile': {'cmd': 'echo',
                                        'when' : 'today',
                                        # 'days' : '1-5',
                                        'start_time' : '20:00:00',
                                        'end_time' : '21:00:00',
                                        'args': ['$filename', 'YYYYMMDD']}},]
                    },},
                                   'recurse' : False,
                                   }
                  }
    # '/tmp/testdir' : {'name': 'Other file',
    #                                 'filemasks': { ,
    #                                 'recurse': False,
    #                                 }
    # {'processFile': {'cmd': 'process', 'args': ['$filename', 'YYYYMMDD']}}
    # watch_data = { '/tmp/' : { 'name' : 'Fake', 'filemasks' : { 'somefilemask' : { 'actions' : [] } } } }
    # watcher = Watcher(watch_data, callback_func = callback_func)
    watcher = Watcher(watch_data)
    while 1:
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    _setup_logger(logger)
    test()
