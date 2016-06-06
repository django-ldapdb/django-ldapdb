#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This software is distributed under the two-clause BSD license.
# Copyright (c) The django-ldapdb project

import os
import sys

import django
from django.core.management import execute_from_command_line

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "examples.settings")

def run_tests():
    execute_from_command_line([os.path.abspath(__file__), 'test'])
    sys.exit(0)

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
