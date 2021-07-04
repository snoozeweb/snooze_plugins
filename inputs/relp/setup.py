from setuptools import setup, find_packages

setup(
    name='snooze-relp',
    version='1.0.0',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="Syslog input plugin for snooze server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=url,
    packages=find_packages(include=['snooze_relp', 'snooze_relp.*']),
    entry_points={
        'console_scripts': [
            'snooze-syslog = snooze_relp.main:main',
        ],
    },
    install_requires = [
        'PyYAML',
        'pathlib',
        'relp',
        'snooze-client',
    ],
    classifiers=[],
)
