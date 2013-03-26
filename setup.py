from distutils.core import setup
from setuptools import find_packages

setup(name='cronify',
      version='0.1',
      description="Event based cron-like utility using the linux kernels' inotify API",
      author='Panos Kittenis',
      author_email='pkittenis@gmail.com',
      url = "https://github.com/pkittenis/cronify",
      packages = find_packages('.'),
      install_requires = ['pyinotify', 'pyaml', 'python-daemon'],
      classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Intended Audience :: Developers, Systems Operations',
        'Programming Language :: Python',
        'Topic :: Task Schedulers',
          ],
      data_files = [('/etc/init.d', ['cronifyd'])],
      )
