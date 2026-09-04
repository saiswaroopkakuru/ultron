from setuptools import setup, find_packages

setup(
    name="ultron",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "ultron=ultron.cli:main",
        ],
    },
)
