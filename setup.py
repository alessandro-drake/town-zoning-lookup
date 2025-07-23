# setup.py

from setuptools import setup, find_packages

setup(
    name='town-zoning-lookup',
    version='0.1.0',
    packages=find_packages(),
    py_modules=[
        'ordinance_finder',
        'analysis_api',
        'best_practices',
        'main'
    ],
)