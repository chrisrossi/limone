import os
import platform
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.rst')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()
except IOError:
    README = CHANGES = ''

install_requires = [
    'colander',
    ]

tests_require = install_requires

if sys.version_info[:2] < (2, 7):
    test_requires += ['unittest2']

setup(name='limone',
      version='0.1',
      description=('Content type system based on colander schemas.'),
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Framework :: Pylons",
        "License :: Repoze Public License",
        ],
      keywords='',
      author="Chris Rossi, Archimedean Company",
      author_email="pylons-devel@googlegroups.com",
      url="http://pylonsproject.org",
      license="BSD-derived (http://www.repoze.org/LICENSE.txt)",
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires = install_requires,
      tests_require = tests_require,
      test_suite="limone.tests",
      entry_points = """\
      """
      )
