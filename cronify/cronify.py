# This file is part of cronify

# Copyright (C) 2016 Panos Kittenis

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, version 2.1.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


"""Main cronify package. Contains main Watcher class and EventHandler"""


import os
import pyinotify
import time
import fnmatch
import logging
import sys
from pythonlibraries import threadpool
import subprocess
import pytz
import datetime
import re
import signal
import asyncore
import threading
from common import read_cfg, CFG_FILE, _MASKS

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
    proc = subprocess.Popen(cmd_args, shell=False, stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout, stderr


class EventHandler(pyinotify.ProcessEvent):
    """:mod:`pyinotify.ProcessEvent` subclass, implements handlers for our actions.
    
    Triggers actions on events that match our filemasks, queues/runs actions and
    outputs action results
    """
    
    _filename_keyword = '$filename'
    _datestamp_re = r'\d{4}\d{2}\d{2}'
    _datestamp_rc = re.compile(_datestamp_re)
    _datestamp_keyword_fmt = ( 'YYYYMMDD', '%Y%m%d' )
    
    # filemasks_actions = {
    # 'somefile.txt' : [ { 'action1' : { 'cmd' : 'echo', <..> }, 'actionN' : <..> } ],
    # 'otherfile.txt' : [ { 'action1' : { 'cmd' : 'cat', <..> }, 'actionN' : <..> } ],
    # }
    def __init__(self, filemask_actions, thread_pool,
                 callback_func=None,
                 file_tz=None,
                 local_tz=None):
        pyinotify.ProcessEvent.__init__(self)
        self.filemask_actions, self.thread_pool = filemask_actions, thread_pool
        self.callback_func = callback_func
        for filemask in self.filemask_actions.copy():
            new_filemask = self._parse_filemask(filemask)
            self.filemask_actions[new_filemask] = self.filemask_actions[filemask]
            del self.filemask_actions[filemask]
        self.file_tz = file_tz
        self.local_tz = local_tz
        logger.debug("Got local tz %s", (self.local_tz,))
    
    def process_IN_CLOSE_WRITE(self, event):
        """IN_CLOSE_WRITE event handler
        Just redirects to self.handle_event"""
        self.handle_event(event)
    
    def process_IN_MOVED_FROM(self, event):
        """IN_MOVED_FROM event handler
        Just redirects to self.handle_event"""
        self.handle_event(event)
    
    def handle_event(self, event):
        """Check triggered event against filemask, do actions if filemask is accepted"""
        for filemask in self.filemask_actions:
            if not filemask.match(event.name):
                logger.debug("Filename %s did not match filemask pattern %s", event.name, filemask.pattern,)
                continue
            logger.debug("Matched filename %s with filemask %s from event %s", event.name, filemask.pattern, event.maskname,)
            self.thread_pool.add_task_to_queue(self.do_actions, event, self.filemask_actions[filemask]['actions'])
    
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
                logger.debug("Parsed datestamp %s for file %s", file_datestamp.strftime(self._datestamp_keyword_fmt[1]),
                            event.pathname,)
                action_args[i] = file_datestamp.strftime(self._datestamp_keyword_fmt[1])
                file_metadata['datestamp'] = file_datestamp
        return action_args, file_metadata

    def _parse_action_metadata(self, action):
        """Parse action constraints and return metadata"""
        metadata = {}
        for key in action:
            if key == 'start_time':
                metadata['start_time'] = self._parse_isoformat_time(action[key])
                logger.debug("Parsed action start time %s", (metadata['start_time'],))
            elif key == 'end_time':
                metadata['end_time'] = self._parse_isoformat_time(action[key])
                logger.debug("Parsed action end time %s", (metadata['end_time'],))
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
            logger.debug("Parsed file datestamp from date in filename - %s from %s", file_datestamp, filename,)
        return datetime.date(file_datestamp.year, file_datestamp.month, file_datestamp.day)

    def do_actions(self, event, actions):
        """Perform actions"""
        logger.debug("Starting actions %s", (actions,))
        [self._do_action(event, action, action_data) for action in actions
         for action_data in action.itervalues()]

    def _do_action(self, event, action, action_data):
        """Perform a single action"""
        action_metadata = self._parse_action_metadata(action_data)
        action_args, file_metadata = self._parse_action_args(event, action_data['args'][:])
        logger.debug("Made expanded action arguments %s", (action_args,))
        action_args.insert(0, action_data['cmd'])
        if action_metadata and 'start_time' in action_metadata and 'end_time' in action_metadata:
            utc = datetime.datetime.utcnow()
            now = datetime.datetime(utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second,
                                    tzinfo = pytz.utc)
            logger.debug("Local tz is %s", (self.local_tz,))
            if self.local_tz:
                now = self.local_tz.normalize(now.astimezone(self.local_tz))
                # Convert tz-aware datetime into naive datetime or datetime arithmetic will fail
                now = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute, now.second)
                logger.debug("Have local_tz configuration, converted 'now' time to %s",
                             (now,))
            else:
                logger.debug("No local_tz config, using system timezone")
                # now is UTC, need naive datetime
                now = datetime.datetime.now()
            start_time = datetime.datetime(file_metadata['datestamp'].year, file_metadata['datestamp'].month,
                                           file_metadata['datestamp'].day, action_metadata['start_time'].hour,
                                           action_metadata['start_time'].minute, action_metadata['start_time'].second)
            end_time = datetime.datetime(file_metadata['datestamp'].year, file_metadata['datestamp'].month,
                                         file_metadata['datestamp'].day, action_metadata['end_time'].hour,
                                         action_metadata['end_time'].minute, action_metadata['end_time'].second)
            if now < start_time:
                logger.info("Action start time %s is in the future, waiting for %s hh:mm:SS",
                            start_time, start_time - now,)
                time.sleep((start_time - now).seconds)
            elif now > start_time and now > end_time:
                logger.info("Action start time %s is in the past and end time %s has passed, not triggering action",
                            start_time, end_time)
                return
        if self.callback_func:
            self.callback_func(event)
        returncode, stdout, stderr = run_script(action_args)
        logger.info("Got result from action %s - %s", action_data, stdout,)
        if returncode:
            logger.error("Action %s failed with exit code %s, stderr %s",
                         action, returncode, stderr,)


class Watcher(object):
    
    """Watcher class to watch a directory and trigger actions"""
    
    _req_data_fields = [ 'name', 'filemasks' ]
    _req_filemask_fields = [ 'actions' ]
    _req_action_fields = [ 'cmd', 'args' ]
    _req_time_fields = ['start_time', 'end_time']
    
    def __init__(self, watch_data,
                 callback_func=None,
                 num_workers=10):
        """
        Start a watcher with watch data
        
        :param watch_data: Dictionary with watch data to use \
        Can have multiple directories to watch as well as multiple filemasks per directory and multiple actions per filemask
        :type watch_data: dict
        :param callback_func: Optional callback function to be called when an action is triggered. \
        There should be only one positional parameter in callback_func for the event object to be passed in
        :type callback_func: function
        :param num_workers: Number of worker threads in actions worker queue

        For example ::
        
          watch_data = {'/tmp/testdir': {
                        'name': 'Some file',
                        'filemasks': { 'somefile.txt' : {
                        'actions': [ { 'echoFile': {
                                       'cmd' : 'echo',
                                       'args' : [
                                       '$filename', 'YYYYMMDD' ] }
                                      },
                                   ]
                        }}}}
        
        """
        self.watch_managers, self.notifiers = [], []
        self.callback_func = callback_func
        if not self.check_watch_data(watch_data):
            logger.critical("Bad configuration, cannot start")
            sys.exit(1)
        self.watch_data = watch_data
        [self._check_timezone_info(self.watch_data[watch]) for watch in self.watch_data]
        self.thread_pool = threadpool.ThreadPool(num_workers=num_workers)
        self.start_watchers(self.watch_data)
        signal.signal(signal.SIGUSR1, self.reload_signal_handler)
        self.asyncore_thread = None

    def _asyncore_target_thread(self):
        """Target function for per watcher asyncore loop thread"""
        while True:
            asyncore.loop()

    def reload_signal_handler(self, signalnum, frame):
        """Signal handler for reloading configuration file and watchers"""
        logger.info("Reloading watchers from configuration file %s", (CFG_FILE,))
        self.update_watchers()

    def check_watch_data(self, watch_data):
        """Check that watch_data is valid
        
        :rtype: bool
        :return: True if watch_data is valid, False otherwise
        """
        if not self._check_data_fields(watch_data, self._req_data_fields):
            return False
        try:
            if False in [False for watch in watch_data
                         if not self._check_data_fields(watch_data[watch]['filemasks'],
                                                        self._req_filemask_fields)]:
                return False
            if False in [False for watch in watch_data for filemask in watch_data[watch]['filemasks']
             if not watch_data[watch]['filemasks'][filemask]['actions']]:
                return False
            if False in [False for watch in watch_data for filemask in watch_data[watch]['filemasks']
                         for action in watch_data[watch]['filemasks'][filemask]['actions']
                         if not self._check_data_fields(action, self._req_action_fields)]:
                return False
            if False in [False for watch in watch_data for filemask in watch_data[watch]['filemasks']
                         for action in watch_data[watch]['filemasks'][filemask]['actions']
                         if (self._req_time_fields[0] in action.values()[0]
                             or self._req_time_fields[1] in action.values()[0])
                         and not self._check_data_fields(action, self._req_time_fields)]:
                return False
        except TypeError:
            logger.critical("Missing required configuration, exiting")
            return False
        return True

    def _check_data_fields(self, data, req_fields):
        """Check for required data fields
        
        :type: dict
        :param data: Dictionary containing data to check
        :type: list
        :param req_fields: List of required fields that are required in data dictionary
        :rtype: bool
        :returns: False if any required fields are missing
        :returns: True if all required fields are present
        """
        if not data:
            logger.critical("Configuration data for %s is empty, cannot continue", (req_fields,))
            return False
        for _key in data:
            if not [True for field in req_fields if field in data[_key]] == [True for field in req_fields]:
                logger.critical("Configuration data for %s is missing required fields from %s. Data is %s",
                                _key, req_fields, data[_key],)
                return False
        return True

    def start_watchers(self, watch_data):
        """Go through watch_data and start watchers"""
        for watcher in watch_data:
            watch_dir = self._check_dir(watcher)
            if not watch_dir:
                logger.critical("Desired directory to watch %s does not exist or is not a directory. Exiting.", (watcher,))
                sys.exit(1)
            recurse = watch_data[watcher]['recurse'] if 'recurse' in watch_data[watcher] else False
            watch_manager = pyinotify.WatchManager()
            local_tz = watch_data[watcher]['local_tz'] if 'local_tz' in watch_data[watcher] else None
            notifier = pyinotify.AsyncNotifier(watch_manager, EventHandler(watch_data[watcher]['filemasks'].copy(),
                                                                           self.thread_pool,
                                                                           callback_func = self.callback_func,
                                                                           local_tz = local_tz
                                                                           ))
            watch_manager.add_watch(watch_dir, _MASKS, rec = recurse, auto_add = True)
            logger.info("Started watching directory %s with filemasks and actions %s, recurse %s..",
                        watch_dir,
                        watch_data[watcher]['filemasks'],
                        recurse,)
            self.notifiers.append(notifier)
            self.watch_managers.append(watch_manager)
        self.asyncore_thread = threading.Thread(target = self._asyncore_target_thread)
        self.asyncore_thread.daemon = True
        self.asyncore_thread.start()

    def update_watchers(self, watch_data=None):
        """
        Try and update watchers with new watch_data.
        Watch data is re-read from cfg file if not provided
        """
        if not watch_data:
            watch_data = read_cfg(open(CFG_FILE, 'r'))
        if not watch_data:
            logger.error("Could not read configuration file or invalid configuration in file")
            return
        if not self.check_watch_data(watch_data):
            logger.error("Invalid configuration found, cannot continue with watcher reload")
            return
        for watcher in watch_data:
            watch_dir = self._check_dir(watcher)
            if not watch_dir:
                logger.critical("Desired directory to watch %s does not exist or is not a directory, cannot continue with watcher reload.",
                                (watcher,))
        self.cleanup()
        self.start_watchers(watch_data)
        self.watch_data = watch_data
        logger.info("Watchers finished reloading..")

    def _check_timezone_info(self, watch_data):
        """Check if we have timezone configuration in watch data, parse if needed"""
        if not 'file_tz' in watch_data and not 'local_tz' in watch_data:
            return
        for tz_key in ['file_tz', 'local_tz']:
            if tz_key in watch_data:
                try:
                    watch_data[tz_key] = pytz.timezone(watch_data[tz_key])
                except pytz.UnknownTimeZoneError:
                    logger.error("Invalid timezone %s given as '%s' configuration, cannot continue",
                                 watch_data[tz_key], tz_key,)
                    sys.exit(1)
                else:
                    logger.debug("Got timezone configuration for %s = %s", tz_key, watch_data[tz_key],)

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
        self.watch_managers, self.notifiers = [], []
        del self.asyncore_thread

def _callback_func(event):
    """Test function for callback_func optional parameter of Watcher class"""
    print "Got event for %s" % (event.name,)

def test():
    """Run with some test watch data when executed as a script"""
    watch_data = {'/tmp/testdir': {'name': 'Some file',
                                   'filemasks': {
                'somefile.*' : {
                    'actions': [
                        { 'checkFile': {
                                'cmd': 'echo',
                                # 'when' : 'today',
                                # 'days' : '1-5',
                                # 'start_time' : '20:00:00',
                                # 'end_time' : '21:00:00',
                                'args': ['$filename', 'YYYYMMDD']}},]
                    }, } },
                  '/tmp/otherdir' : {'name': 'Other file',
                                     'local_tz' : 'US/Eastern',
                                     'filemasks': {
                'otherfile.*' : {
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
    watcher = Watcher(watch_data)
    while 1:
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            watcher.cleanup()
            sys.exit(0)

if __name__ == "__main__":
    _setup_logger(logger)
    test()
