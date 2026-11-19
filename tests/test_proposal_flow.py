import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/factory/skills/factory/scripts'


class ProposalFlow(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'contract.md').write_text('Current contract')
        self.git('add', '.')
        self.git('commit', '-qm', 'Baseline')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()

    def command(self, script, *args, ok=True):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / (script + '.py')), *args],
                                cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(ok, result.returncode == 0, result.stderr)
        return result.stdout if ok else result.stderr

    def factory(self, *args, **kw):
        return self.command('factory', *args, **kw)

    def accept(self, job):
        self.factory('claim', job, 'owner')
        self.factory('intake', job, 'owner', 'accept', '--agent', 'analyst',
                     '--skill', 'factory-analysis', '--evidence', 'Read contract and reproduced mismatch')

    def test_proposal_requires_report_and_receipt_then_rechecks_for_implementation(self):
        job = json.loads(self.factory('add', 'analysis', 'Find a solution', '--proposal'))
        self.assertTrue(job['design_only'])
        self.accept('analysis')
        self.factory('move', 'analysis', 'owner', 'build', ok=False)
        self.factory('move', 'analysis', 'owner', 'ok', ok=False)
        artifact = self.repo / '.git/factory/artifacts/analysis/analysis.md'
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('Proposed fix for the lookup.')
        self.command('proposal', 'record', 'analysis', 'owner', 'pending',
                     '--source', 'contract.md', '--reason', 'Partner fixture unavailable')
        self.factory('move', 'analysis', 'owner', 'ok')
        (self.repo / 'contract.md').write_text('Updated contract')
        self.git('commit', '-qam', 'Update contract')
        self.factory('add', 'fix', 'Implement the recommendation', '--after', 'analysis')
        self.accept('fix')
        self.factory('move', 'fix', 'owner', 'build', ok=False)
        changes = json.loads(self.command('proposal', 'status', 'fix'))['parents']['analysis']
        self.assertEqual(set(changes), {'file:contract.md'})
        resume = json.loads(self.command('resume', 'fix'))
        self.assertEqual(resume['action'], 'recheck_proposal')
        self.assertEqual(resume['parents'], {'analysis': changes})
        self.command('proposal', 'recheck', 'fix', 'owner', 'analysis', 'file:contract.md',
                     '--observed', changes['file:contract.md'], '--evidence', 'Reviewed updated contract')
        self.assertEqual(json.loads(self.command('resume', 'fix'))['action'], 'design')
        self.assertEqual(json.loads(self.factory('move', 'fix', 'owner', 'build'))['stage'], 'build')

    def test_legacy_design_job_can_close_without_proposal(self):
        self.factory('add', 'diag', 'Diagnose', '--design-only')
        self.accept('diag')
        self.assertEqual(json.loads(self.factory('move', 'diag', 'owner', 'ok'))['stage'], 'ok')
