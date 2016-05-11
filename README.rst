cronify
============

Cronify is a file event based task scheduler that uses the Linux kernels' inotify API. An Inotify cron implementation if you will.

It allows for triggering of actions when a file event occurs, with configurable action parameters that can be file data such as file name and file datetime and for scheduling actions to be run within a certain time period among other things.

Once installed, it is run as a service, or daemon, much like cron itself. Cronify may also be used as a python library.

The service's configuration is YAML based.

.. image:: https://api.travis-ci.org/pkittenis/cronify.png?branch=master
	:target: https://travis-ci.org/pkittenis/cronify

************
Installation
************

Requires a running Linux kernel >=2.6.13

::

	$ sudo pip install cronify
	$ sudo chmod +x /etc/init.d/cronifyd
	# Install a /etc/cronify.yaml file as in the examples below
	# Once a configuration file is in place, start the cronify daemon with the provided init script
	$ sudo /etc/init.d/cronifyd start

***********************
Configuration Example
***********************

``$ cat /etc/cronify.yaml``

.. code-block:: yaml

	/tmp/testdir :
	    name : Access log watcher
	    recurse : false
	    filemasks :
	      somefile.* :
	        actions :
	          - processFile :
	              args:
	                - $filename
	                - YYYYMMDD
	              cmd: echo

::

	$ sudo /etc/init.d/cronifyd start
	$ touch /tmp/testdir/somefile.txt
	$ tail /var/log/cronify/cronify.log

	cronify.cronify - Thread-1 - 2013-03-26 17:40:40,485 - INFO - Got result from action {'cmd': 'echo', 'args': ['echo', '/tmp/testdir/somefile.txt', '20130326']} - /tmp/testdir/somefile.txt 20130326


***********************************************************************
More complex configuration with multiple watchers and delayed actions
***********************************************************************

See example.yaml in repository for complete list of accepted configuration


``$ cat /etc/cronify.yaml``

.. code-block:: yaml

	/tmp/testdir :
	    name : Access log watcher
	    recurse : false
	    filemasks :
	      access_log_YYYYMMDD.* :
	        actions :
	          - processFile :
	              args:
	                - $filename
	                - YYYYMMDD
	              cmd: process

	/tmp/testdir2 :
	    name : Other log watcher
	    recurse : true
	    filemasks :
	      other_log_YYYYMMDD.* :
	         actions :
	          # Actions to perform on the file in sequence.
	          - processFile :
	            # Do not start action before this time. Action is queued until start_time if triggered prior to it.
	            # This configuration setting is optional
	            start_time: 0800
	            # Do not start action after this time. Action is queued until next start_time if triggered after end time
	            # This configuration setting is optional
	            end_time: 1000
	            args:
	              - $filename
	              - YYYYMMDD
	            cmd: process


*******************
Known limitations
*******************

- Currently queued actions will be _lost_ upon a service restart.

- When using recurse, inotify is limited to watching N number of subdirectories in the tree, where N is value of /proc/sys/fs/inotify/max_user_watches. See http://linux.die.net/man/7/inotify

  User can increase this limit by modifying /proc/sys/fs/inotify/max_user_watches

- When watching an NFS directory on NFS server side, only events made by the NFS *server* will be seen by the inotify API and following, cronify itself.

  When watching an NFS directory on NFS client side, no events are seen by inotify at all.

  In other words if you were planning on watching for a file that is created by an NFS *client*, this is currently not possible.

.. image:: https://cruel-carlota.pagodabox.com/f1d73b292eef6e399205a85d1bc7657b
   :alt: githalytics.com
   :target: http://githalytics.com/pkittenis/cronify
