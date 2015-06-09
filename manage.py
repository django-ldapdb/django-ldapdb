#!/usr/bin/env python
import os
import sys

import django
from django.core.management import execute_from_command_line

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

def run_tests():
    if django.VERSION < (1, 6):
        execute_from_command_line([os.path.abspath(__file__), 'test', 'ldapdb', 'examples'])
    else:
        execute_from_command_line([os.path.abspath(__file__), 'test'])
    sys.exit(0)

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
