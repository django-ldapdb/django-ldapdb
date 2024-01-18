PACKAGE := ldapdb
TESTS_DIR := examples

# Error on all warnings, except in python's site.py module and distutils' imp.py module.
PYWARNINGS = -Wdefault::DeprecationWarning

default:

install:
	python setup.py install

clean:
	find . -type f -name '*.pyc' -delete
	find . -type f -path '*/__pycache__/*' -delete
	find . -type d -empty -delete

upgrade:
	pip install --upgrade pip setuptools
	pip install --upgrade -e .[dev]
	pip freeze

release:
	fullrelease


.PHONY: default install clean upgrade release

testall:
	tox

test:
	python $(PYWARNINGS) manage_dev.py test

.PHONY: test testall

lint: flake8 isort check-manifest

flake8:
	flake8 $(PACKAGE) $(TESTS_DIR)

isort:
	isort $(PACKAGE) $(TESTS_DIR) --check-only --diff --project $(PACKAGE) --project $(TESTS_DIR)

check-manifest:
	check-manifest

.PHONY: isort lint flake8 check-manifest
