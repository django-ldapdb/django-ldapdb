PACKAGE := ldapdb

CODE_DIRS := $(PACKAGE)/


default: test


test:
	tox


lint:
	flake8 $(CODE_DIRS)

