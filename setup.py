"""A Git LFS server implementation

Implements the API described here:
https://github.com/git-lfs/git-lfs/tree/master/docs/api
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='py-git-lfs',

    version='0.0.1',

    description='Git LFS server implementation',
    long_description=long_description,

    url='https://github.com/TouchSurgery/py-git-lfs',

    author='Hansel Dunlop',
    author_email='hansel@touchsurgery.com',

    license='MIT',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Version Control :: Git',
        'Framework :: Django',
        'Framework :: Flask',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

    keywords='git git-lfs large file storage',

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=['peppercorn'],

    # You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': ['check-manifest'],
        'test': ['coverage'],
    },

    entry_points={
        'console_scripts': [
            'git-lfs-authenticate=lfs.auth:ssh_auth',
        ],
    },
)
