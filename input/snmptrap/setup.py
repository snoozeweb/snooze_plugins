from setuptools import setup, find_packages

url = "https://github.com/Nemega/snooze"

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='snooze-snmptrap',
    version='1.0.4',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="SNMPTrap input plugin for snooze server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=url,
    packages=find_packages(include=['snooze_snmptrap', 'snooze_snmptrap.*']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    entry_points={
        'console_scripts': [
            'snooze-snmptrap = snooze_snmptrap.main:main',
        ],
    },
    install_requires=[
        'snooze-client',
        'PyYAML',
        'pathlib',
        'pysnmp',
    ],
)
