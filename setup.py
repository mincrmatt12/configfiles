from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_desc = f.read()

with open("requirements.txt", "r") as f:
    reqs = f.readlines()
    reqs = [x.rstrip("\n") for x in reqs]

setup(
    name="configfiles",
    version="0.2.0",
    packages=find_packages(),
    install_requires=reqs,

    author="Matthew Mirvish",
    description="A tool to manage config files across machines.",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    license="MIT",
    keywords="vcs configuration remote tool cli config management",
    url="https://github.com/mincrmatt12/configfiles",
    project_urls={
        "Bug Tracker": "https://github.com/mincrmatt12/configfiles/issues",
        "Source Code": "https://github.com/mincrmatt12/configfiles"
    },

    entry_points={
        'console_scripts': [
            'configfiles = configfiles.__main__:cli'
        ]
    }
)
