from __future__ import absolute_import

import os
import subprocess
import signal
import time

try:
    import setproctitle
    HAS_PROC = True
except ImportError:
    HAS_PROC = False

import salt.config
import salt.utils.master as master

from tests.support.unit import skipIf
from tests.support.case import ShellTestCase
from tests.support.paths import TMP_ROOT_DIR
from tests.support.runtests import RUNTIME_VARS

DEFAULT_CONFIG = salt.config.master_config(None)
DEFAULT_CONFIG['cachedir'] = os.path.join(TMP_ROOT_DIR, 'cache')


@skipIf(not HAS_PROC, "setproctitle necessary to run integration tests")
class MasterUtilJobsTestCase(ShellTestCase):

    def setUp(self):
        # Necessary so that the master pid health check 
        # passes as it looks for salt in cmdline
        setproctitle.setproctitle('salt')

    def test_get_running_jobs(self):
        ret = self.run_run_plus("test.sleep", '90', async=True)
        jid = ret['jid']
        time.sleep(2)
        jobs = master.get_running_jobs(DEFAULT_CONFIG)
        assert any([job['jid'] == jid for job in jobs])
         
