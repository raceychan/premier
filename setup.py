import codecs
import pathlib

from setuptools import find_packages, setup

PROJECT_NAME = "premier"
PROJECT_ROOT = pathlib.Path.cwd()
URL = f"https://github.com/raceychan/{PROJECT_NAME}"
VERSION = "0.0.1"
DESCRIPTION = "an intuitive throttler supports distributed usage and various throttling algorithms"


with codecs.open(str(PROJECT_ROOT / "README.md"), encoding="utf-8") as fh:
    long_description = "\n" + fh.read()

setup(
    name=PROJECT_NAME,
    version=VERSION,
    package_dir={"": f"{PROJECT_NAME}"},
    url=URL,
    packages=find_packages(
        where=f"{PROJECT_NAME}", exclude=["tests", "*.tests", "*.tests.*", "tests.*"]
    ),
    install_requires=["redis>=5.0.3"],
    # extras_require={"redis": ["redis"]},
    description=DESCRIPTION,
    long_description_content_type="text/markdown",
    long_description=long_description,
    author="race",
    author_email="raceychan@gmail.com",
    license="MIT",
    python_requires=">=3.9",
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
