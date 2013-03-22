cronify
============

Cronify is an event based task scheduler that uses the Linux kernels' inotify API.

It allows for triggering of actions when files appear in a directory, with configurable action parameters that can be file data such as file name and file date stamp and for scheduling actions to be run within a certain time period among other things.

The service's configuration is YAML based. You may of course run cronify as a python module as well.

Once installed, it is run as a service, or daemon, much like cron itself.

.. image:: https://api.travis-ci.org/pkittenis/cronify.png?branch=master
	:target: https://travis-ci.org/pkittenis/cronify

************
Installation
************

Requires a running Linux kernel >=2.6.13

::
	$ pip install cronify

************
Configuration Example
************

>>>
