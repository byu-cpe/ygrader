IN_ENV = if [ -e .venv/bin/activate ]; then . .venv/bin/activate; fi;

package:
	python setup.py sdist
	twine upload dist/*

test: 
	cd test && python3 -m unittest

doc:
	cd doc && make html

lint:
	pylint ygrader

env:
	python3 -m venv .venv
	$(IN_ENV) pip install -r requirements.txt


.PHONY: test doc