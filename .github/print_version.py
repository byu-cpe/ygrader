import pkg_resources  # part of setuptools

version = pkg_resources.require("ygrader")[0].version
print(version)
