'''Setup of the python package'''

from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='snooze-smtp',
    version='1.0.8',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="SMTP input plugin for snooze server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['snooze_smtp', 'snooze_smtp.*']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    entry_points={
        'console_scripts': [
            'snooze-smtp = snooze_smtp.main:main',
        ],
    },
    install_requires=[
        'snooze-client',
        'PyYAML',
        'pathlib',
    ],
)
