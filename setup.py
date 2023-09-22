from setuptools import setup

setup(
    name="ygrader",
    packages=["ygrader"],
    version="1.1.22",
    description="Grading scripts used in BYU's Electrical and Computer Engineering Department",
    author="Jeff Goeders",
    author_email="jeff.goeders@gmail.com",
    license="MIT",
    url="https://github.com/byu-cpe/ygrader",
    install_requires=["pandas>=1.0.0"],
)
