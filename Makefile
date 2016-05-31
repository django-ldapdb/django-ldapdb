PACKAGE := ldapdb

CODE_DIRS := $(PACKAGE)/


default: test


testall:
	tox

test:
	python -Wdefault manage.py test

lint:
	flake8 $(CODE_DIRS)

install-deps:
	pip install -r requirements_dev.txt
