from setuptools import setup

setup(
    name='asyncbb-eth',
    version='0.0.1',
    author='Tristan King',
    author_email='tristan.king@gmail.com',
    packages=['asyncbb.ethereum', 'asyncbb.ethereum.test'],
    url='http://github.com/tristan/asyncbb-eth',
    description='',
    long_description=open('README.md').read(),
    install_requires=[
        'regex',
        'asyncbb',
        'ethutils',
        'ethereum',
        'rlp==0.4.6'
    ],
    dependency_links=[
        'http://github.com/tristan/asyncbb/tarball/master#egg=asyncbb',
        'http://github.com/tristan/ethutils/tarball/master#egg=ethutils'
    ],
    setup_requires=['pytest-runner'],
    tests_require=[
        'pytest',
        'testing.common.database'
    ]
)
