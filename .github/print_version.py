import pkg_resources  # part of setuptools

version = pkg_resources.require("yaccounts")[0].version
print(version)
