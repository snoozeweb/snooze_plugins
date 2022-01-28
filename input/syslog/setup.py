from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='snooze-syslog',
    version='1.0.7',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="Syslog input plugin for snooze server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['snooze_syslog', 'snooze_syslog.*']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    entry_points={
        'console_scripts': [
            'snooze-syslog = snooze_syslog.main:main',
        ],
    },
    install_requires = [
        'snooze-client',
        'PyYAML',
        'pathlib',
    ],
)
