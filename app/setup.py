from setuptools import setup, find_packages

setup(
    name='minilims',
    version='0.2',
    description='Simple Laboratory Information Management System made for Statens Serum Institut',
    # url='',
    author="Martin Basterrechea",
    author_email="mbas@ssi.dk",
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=[
        'Flask',
        'Flask-PyMongo',
        'requests',
        'watchdog',
        'pymodm',
        # And for the steps.
        'openpyxl',
        'pandas',
        # For running the server
        'gunicorn'
    ],
    scripts=['bin/minilims']
)
