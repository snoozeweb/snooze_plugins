from setuptools import setup, find_packages

version = '1.5.0'

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="snooze-patlite",
    version=version,
    description='Patlite plugin for Snooze',
    url='https://github.com/snoozeweb/snooze',
    author='Florian Dematraz, Guillaume Ludinard',
    author_email='snooze@snoozeweb.net',
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(include=['patlite', 'patlite.falcon', 'patlite.utils']),
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
    ],
    package_data={
        '': [
            '*.yaml',
        ],
    },
    include_package_data=True,
    install_requires=[
    ],
    entry_points={
        'snooze.plugins.core': [
            'patlite = patlite.plugin:Patlite',
        ]
    }
)
