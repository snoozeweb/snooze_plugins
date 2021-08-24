from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name='snooze-pacemaker',
    version='1.0.2',
    author='Guillaume Ludinard, Florian Dematraz',
    author_email='guillaume.ludi@gmail.com, ',
    description="Snooze input plugin for pacemaker alerts",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['snooze_pacemaker', 'snooze_pacemaker.*']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    entry_points={
        'console_scripts': [
            'snooze-pacemaker = snooze_pacemaker.main:alert',
        ],
    },
    install_requires = [
        'snooze-client',
        'python-dateutil',
    ],
)
