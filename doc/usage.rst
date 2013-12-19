====================
Cronify daemon usage
====================


Installation
-------------

Requires a running Linux kernel >=2.6.13 with inotify support.

::

	$ sudo pip install cronify
	$ sudo chmod +x /etc/init.d/cronifyd


Install configuration file
--------------------------

Configuration file is written in yaml and looks like

.. code-block:: yaml

	<directory to watch> :
	  name: <name of watcher>
	  <optional> recurse: false
	  filemasks:
	    <filemask1> :
	      actions :
	       - <action1> :
	         cmd : <executable>
	         args:
		   - <argument1>
		   - <argument2>
		   - <argumentN>
	       - <actionN> :
	         <..>
	    <filemaskN> :
	      <..>

Recurse is optional, defaulting to off, and if turned on the watcher will recursively watch all subdirectories for matching filemasks.

When using recurse, inotify is limited to watching N number of subdirectories in the tree, where N is value of /proc/sys/fs/inotify/max_user_watches. See http://linux.die.net/man/7/inotify

User can increase this limit by modifying the value of /proc/sys/fs/inotify/max_user_watches

A given directory configuration can have multiple filemasks and each filemask can have multiple actions with no limits other than required memory to keep state. A single directory may only be defined once, if defined multiple times within a configuration definitions will override previous ones.

Filemasks
---------

Filemasks are filename shell patterns, everything supported on the shell is supported as a filemask.

Additionally, a datestamp pattern may be defined in a filemask and used later as an action argument (see below for action argument listings).

+-------------------+-------------------------------------------------------------------+
| Filemask pattern  | Definition 						        |
+===================+===================================================================+
| YYYYMMDD          | Datestamp of file in the YYYYMMDD format, eg 20050101 	        |
+                   +								        +
|                   | A datestamp *must* exist in the filename for the pattern to match |
+-------------------+-------------------------------------------------------------------+

Actions
-------

Action arguments can be variables, of which two are supported and they are

+-----------+------------------------------------------------------------+
| Variable  | Definition 						 |
+===========+============================================================+
| $filename | Name of file that triggered the action                     |
+-----------+------------------------------------------------------------+
| YYYYMMDD  | Datestamp of file in the YYYYMMDD format, eg 20050101 	 |
+           +								 +
|           | The filemask may contain YYYYMMDD in which 		 |
| 	    | case that is used *instead* of the on-filesystem datestamp |
+           +								 +
|	    | This is intended to support re-running historical actions  |
| 	    | that use a datestamp as an argument 			 |
+-----------+------------------------------------------------------------+

Examples
--------------------


Single directory, single filemask with single action
----------------------------------------------------

.. code-block:: yaml

	/tmp/testdir :
	    name : Fake watcher
	    recurse : false
	    filemasks :
	      somefile.* :
	        actions :
	          - processFile :
		      cmd: echo
	              args:
	                - $filename
	                - YYYYMMDD

Any files matching the 'somefile.*' filemask in the /tmp/testdir directory will trigger the 'echo' command with two arguments, one the filename that triggered the command, the second the datestamp of the file.

Multiple directories, multiple filemasks and actions
----------------------------------------------------

.. code-block:: yaml

	/mnt/access_logs :
	    name : Webserver access and error log watcher
	    filemasks :
	      access_log_YYYYMMDD.* :
	        actions :
	          - parseAccessLog :
		      cmd: prase_access_log
	              args:
	                - $filename
			- YYYYMMDD
	      error_log_YYYYMMDD.* :
	        actions :
		  # Parse error log and send data to monitoring/graphing/alerting service
		  - parseErrorLog :
		      cmd: parse_error_log
		      args:
	                - $filename
			- YYYYMMDD

	/mnt/video_downloads:
	    name : Video download watcher
	    filemasks :
	      *.mp4 :
	        actions:
		  # Re-encode to desired format
		  - reEncode :
		      cmd: reencode_mp4.sh
		      args :
		        - $filename
		  # Move to final location after re-encoding
		  - move:
		      cmd: mv
		      args:
		        - $filename
		        - /mnt/media/completed_videos

In the case of multiple actions, as in *`/mnt/video_downloads`* above, each action will be run sequentially one after the other in the order they are listed in the configuration. In the above example, the *`reEncode`* would be run first, then the *`move`* action.

All actions *must* be valid executables. Shell commands, shell expansions, sequential execution of commands separated by ';' (a shell feature), anything that requires a shell, none of these will work. This is done purposefuly as it is a security risk [#first]_.

.. [#first] https://en.wikipedia.org/wiki/Code_injection#Shell_injection
