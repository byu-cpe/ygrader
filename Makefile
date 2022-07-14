package:
	python setup.py sdist
	twine upload dist/*

test: 
	cd test && python3 -m unittest

doc:
	cd doc && make html

lint:
	pylint ygrader

.PHONY: test doc