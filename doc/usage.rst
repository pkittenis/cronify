====================
Cronify daemon usage
====================


Installation
-------------

Requires a running Linux kernel >=2.6.13

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
	    <filemask> :
	      actions :
	       - <action1> :
	         cmd : <executable>
	         args:
		   - <argument1>
		   - <argument2>
		   - <argumentN>

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
	    name : Access log watcher
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
