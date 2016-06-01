PACKAGE := ldapdb

CODE_DIRS := $(PACKAGE)/


default: test


testall:
	tox

test:
	python -Wdefault manage.py test

lint:
	flake8 $(CODE_DIRS)

