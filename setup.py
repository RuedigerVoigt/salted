#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="salted",
    version="0.6.1",
    author="Rüdiger Voigt",
    author_email="projects@ruediger-voigt.eu",
    description="Smart, Asynchronous Link Tester with Database backend",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/RuedigerVoigt/salted",
    package_data={
        "salted": ["py.typed", "templates/*.jinja"]},
    include_package_data=True,
    packages=setuptools.find_packages(),
    python_requires=">=3.8",
    install_requires=["aiodns>=2.0.0",
                      "aiohttp>=3.7.3",
                      "beautifulsoup4>=4.9.3",
                      "cchardet>=2.1.7",
                      "compatibility>=0.8.0",
                      "jinja2>=2.11.2",
                      "lxml>=4.6.2",
                      "tqdm>=4.54.1",
                      "userprovided>=0.8.0"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        #"Development Status :: 5 - Production/Stable",
        "Development Status :: 4 - Beta",
        "Framework :: AsyncIO",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "Topic :: Internet :: WWW/HTTP :: Site Management :: Link Checking"
    ],
)
