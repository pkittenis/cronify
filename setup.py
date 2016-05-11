# Copyright (C) 2016 Panos Kittenis

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os
import sys
from setuptools import setup, find_packages

with open("README.rst") as file:
    long_desc = file.read()

convert_2_to_3 = {}
if sys.version_info >= (3,):
    convert_2_to_3['use_2to3'] = True

_init_path = '/etc/init.d' if os.getuid() == 0 else 'etc/init.d'
setup(name='cronify',
      version='0.13',
      description="File event based task scheduler using the linux kernel's inotify API",
      long_description=long_desc,
      author='Panos Kittenis',
      author_email='pkittenis@gmail.com',
      url="https://github.com/pkittenis/cronify",
      packages=find_packages('.'),
      license='GPLv2',
      install_requires=['pyinotify', 'PyYAML', 'python-daemon', 'pytz'],
      classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python',
        'Topic :: Utilities',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Utilities',
        'Operating System :: POSIX :: Linux',
          ],
      data_files=[(_init_path, ['cronifyd'])],
      **convert_2_to_3
      )
