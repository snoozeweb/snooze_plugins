from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='snooze-googlechat',
    version='1.0.6',
    author='Florian Dematraz, Guillaume Ludinard',
    author_email='florian.dematraz@snoozeweb.net, ',
    description="Google Chat Bot ouput plugin for snooze server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['snooze_googlechat', 'snooze_googlechat.*']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    entry_points={
        'console_scripts': [
            'snooze-googlechat = snooze_googlechat.main:main',
        ],
    },
    install_requires = [
        'falcon',
        'google-api-python-client',
        'google-cloud-pubsub',
        'protobuf',
        'pyparsing',
        'python-dateutil',
        'pyyaml',
        'snooze-client',
    ],
    extras_require={
        'pyparsing': ['httplib2>=0.20.2'],
    },
)
