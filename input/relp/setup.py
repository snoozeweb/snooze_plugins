from setuptools import setup, find_packages

with open('README.md') as f:
    long_description = f.read()

setup(
    name='snooze-relp',
    version='1.0.1',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="Syslog input plugin for snooze server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['snooze_relp', 'snooze_relp.*']),
    entry_points={
        'console_scripts': [
            'snooze-relp = snooze_relp.main:main',
        ],
    },
    install_requires = [
        'PyYAML',
        'pathlib',
        'relp',
        'snooze-client',
        'snooze-syslog',
    ],
    classifiers=[],
)
