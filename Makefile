PACKAGE := ldapdb
TESTS_DIR := examples

# Error on all warnings, except in python's site.py module and distutils' imp.py module.
PYWARNINGS = -Wdefault -Werror -Wignore::DeprecationWarning:site:165 -Wignore::PendingDeprecationWarning:imp

default:

clean:
	find . -type f -name '*.pyc' -delete
	find . -type f -path '*/__pycache__/*' -delete
	find . -type d -empty -delete

update:
	pip install --upgrade pip setuptools
	pip install -r requirements_dev.txt
	pip freeze

.PHONY: default clean update

testall:
	tox

test:
	python $(PYWARNINGS) manage_dev.py test

.PHONY: test testall

lint: flake8 check-manifest

flake8:
	flake8 --config .flake8 $(PACKAGE) $(TESTS_DIR)

check-manifest:
	check-manifest

.PHONY: lint flake8 check-manifest
