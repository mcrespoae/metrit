from setuptools import setup

VERSION = "0.0.1"
setup(
    name="measurit",
    version=VERSION,
    author="mcrespoae",
    author_email="info@mariocrespo.es",
    packages=["measurit"],
    description="A dead simple resources monitoring decorator",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/mcrespoae/measurit",
    install_requires=["psutil==5.9.8"],
    setup_requires=["psutil==5.9.8"],
    python_requires=">=3.8",
    keywords=["measurit"],
    classifiers=[
        "Development Status :: 1 - Planning",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
    ],
)