#!/usr/bin/env python

import setuptools

with open("README.md") as f_readme:
    long_description = f_readme.read()

setuptools.setup(
    name="pixiv-down",
    version="0.1",
    python_requires=">=3.6",
    author="Seamile",
    author_email="lanhuermao@gmail.com",
    description="Pixiv illusts downloader.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/seamile/pixiv-dl",
    packages=['pixiv_down'],
    install_requires=[
        "PixivPy>=3.6.0",
        "requests>=2.26.0",
    ],
    entry_points={
        'console_scripts': [
            'pixd=pixiv_down.pixiv_down:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Topic :: Utilities',
    ],
)
