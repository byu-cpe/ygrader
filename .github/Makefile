IN_ENV := . .venv/bin/activate;

env:
	python3 -m venv .venv
	$(IN_ENV) pip3 install packaging

check_version_increase:
	$(IN_ENV) pip uninstall -y ygrader
	$(IN_ENV) pip install ygrader
	$(IN_ENV) echo `python print_version.py` > pypi_version.txt
	$(IN_ENV) pip uninstall -y ygrader
	$(IN_ENV) pip install ..
	$(IN_ENV) echo `python print_version.py` > current_version.txt
	$(IN_ENV) pip uninstall -y ygrader
	$(IN_ENV) python compare_versions.py pypi_version.txt current_version.txt