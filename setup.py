#!/usr/bin/env python3
"""Setup script for promptctl."""

from setuptools import setup, find_packages

setup(
    name="promptctl",
    version="1.0.0",
    description="Git-backed prompt management CLI",
    packages=find_packages(),
    install_requires=[
        "GitPython>=3.1.40",
    ],
    entry_points={
        "console_scripts": [
            "promptctl=promptctl:main",
        ],
    },
    python_requires=">=3.8",
)
