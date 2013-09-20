"""
Enables ./setup.py test
http://gremu.net/blog/2010/enable-setuppy-test-your-django-apps/
"""

import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'
test_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, test_dir)

from django.test.utils import get_runner
from django.conf import settings


def runtests():
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True)
    failures = test_runner.run_tests(['ldapdb', 'examples'])
    sys.exit(bool(failures))

if __name__ == '__main__':
    runtests()
