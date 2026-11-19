"""Exercise the proposal receipt and selective recheck through the shipped CLIs."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/factory/skills/factory/scripts'


class ProposalTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git('init', '-q')
        (self.root/'contract.md').write_text('v1')
        self.git('add', 'contract.md')
        self.git('commit', '-qm', 'initial')
        self.F('add', 'idea', 'Find a solution', '--design-only')
        self.tree = Path(json.loads(self.F('claim', 'idea', 'owner'))['worktree'])
        self.F('intake', 'idea', 'owner', 'accept', '--agent', 'analyst', '--skill', 'factory-analysis', '--evidence', 'Inspected contract')
        self.report = self.root/'.git/factory/artifacts/idea/analysis.md'
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.report.write_text('Report v1')

    def git(self, *args, cwd=None):
        return subprocess.check_output(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *args], cwd=cwd or self.root, text=True).strip()

    def cli(self, script, *args, ok=True):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS/script), *args], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, (args, result.stderr))
        return result.stdout.strip() if ok else result.stderr.strip()

    def F(self, *args, **kwargs):
        return self.cli('factory.py', *args, **kwargs)

    def P(self, *args, **kwargs):
        return self.cli('proposal.py', *args, **kwargs)

    def record(self, mode, *args, **kwargs):
        return self.P('record', 'idea', 'owner', mode, '--source', 'contract.md', *args, **kwargs)

    def child(self):
        self.F('move', 'idea', 'owner', 'ok', '--note', 'report')
        self.F('add', 'fix', 'Fix it', '--after', 'idea')
        return Path(json.loads(self.F('claim', 'fix', 'developer'))['worktree'])

    def changes(self):
        return json.loads(self.P('status', 'fix'))['parents']['idea']

    def recheck(self, key, token, *extra, **kwargs):
        return self.P('recheck', 'fix', 'developer', 'idea', key, '--observed', token, '--evidence', 'Compared current contract and original test', *extra, **kwargs)

    def test_evidence_types_and_clean_commit(self):
        self.record('pending', ok=False)
        self.record('pending', '--reason', 'Partner unavailable')
        self.record('fixture', '--case', 'regression passed', ok=False)
        self.record('fixture', '--case', 'regression passed', '--control', 'unknown key absent')
        sha = self.git('rev-parse', 'HEAD', cwd=self.tree)
        evidence = ['--case', 'regression passed', '--control', 'unknown key absent']
        self.record('commit', '--sha', sha[:7], *evidence, ok=False)
        (self.tree/'untracked').write_text('pending')
        self.record('commit', '--sha', sha, *evidence, ok=False)
        (self.tree/'untracked').unlink()
        self.record('commit', '--sha', sha, *evidence)
        receipt = json.loads(self.F('show', 'idea'))['proposal']
        self.assertEqual((receipt['status'], receipt['sha']), ('commit', sha))
        self.assertEqual(len(receipt['report_sha256']), 64)

    def test_recheck_uses_child_checkout_and_reopens_only_changed_items(self):
        self.record('fixture', '--case', '00123 works', '--control', '00999 absent', '--external', 'Partner decision')
        (self.root/'contract.md').write_text('v2')
        self.git('commit', '-qam', 'new contract')
        tree = self.child()
        changed = self.changes()
        self.assertEqual(set(changed), {'file:contract.md', 'external:Partner decision'})
        self.recheck('external:Partner decision', changed['external:Partner decision'])
        self.assertEqual(set(self.changes()), {'file:contract.md'})
        (tree/'contract.md').write_text('v3')
        self.recheck('file:contract.md', changed['file:contract.md'], ok=False)
        self.recheck('file:contract.md', self.changes()['file:contract.md'])
        self.assertEqual(self.changes(), {})
        self.report.write_text('Corrected report')
        self.assertEqual(set(self.changes()), {'report'})
        observed = self.changes()['report']
        self.recheck('report', observed)
        saved = self.F('show', 'fix')
        self.recheck('report', observed)
        self.assertEqual(saved, self.F('show', 'fix'))
        (tree/'contract.md').unlink()
        self.assertEqual(self.changes(), {'file:contract.md': 'missing'})
        self.recheck('file:contract.md', 'missing')
        self.assertEqual(self.changes(), {})
        (tree/'contract.md').write_text('v3')
        self.assertEqual(set(self.changes()), {'file:contract.md'})

    def test_cannot_record_or_close_with_empty_replaced_or_stale_report(self):
        for content in [b'', b'  \r\n  ', bytes([0xff, 0x80])]:
            with self.subTest(content=content):
                self.report.write_bytes(content)
                self.record('pending', '--reason', 'Partner unavailable', ok=False)
        self.report.write_text('Proposal for original source')
        self.record('pending', '--reason', 'Partner unavailable')
        self.report.write_text('Replaced after checks')
        self.F('move', 'idea', 'owner', 'ok', '--note', 'Delivered', ok=False)
        self.record('pending', '--reason', 'Partner unavailable')
        (self.tree/'contract.md').write_text('Changed after analysis')
        self.F('move', 'idea', 'owner', 'ok', '--note', 'Delivered', ok=False)
        self.record('pending', '--reason', 'Partner unavailable')
        self.F('move', 'idea', 'owner', 'ok', '--note', 'Delivered')

    def test_followup_gate_rechecks_the_actual_child_on_build(self):
        self.record('pending', '--reason', 'Source inspection only')
        tree = self.child()
        self.F('intake', 'fix', 'developer', 'accept', '--agent', 'analyst', '--skill', 'factory-analysis', '--evidence', 'Examined proposal')
        (tree/'contract.md').write_text('Child-specific contract')
        self.F('move', 'fix', 'developer', 'build', ok=False)
        self.recheck('file:contract.md', self.changes()['file:contract.md'])
        self.F('move', 'fix', 'developer', 'build')

    def test_commit_proof_needs_clean_new_revision_and_both_cases(self):
        old = self.git('rev-parse', 'HEAD', cwd=self.tree)
        cases = ('--case', 'lookup of 00123 returns item', '--control', '00999 returns absent')
        self.record('commit', '--sha', old, *cases)
        self.git('commit', '--allow-empty', '-qm', 'advance base')
        tree = self.child()
        current = self.git('rev-parse', 'HEAD', cwd=tree)
        self.assertNotEqual(current, old)
        self.assertEqual(self.changes(), {'commit': current})
        self.F('intake', 'fix', 'developer', 'accept', '--agent', 'analyst', '--skill', 'factory-analysis', '--evidence', 'Examined proposal')
        self.F('move', 'fix', 'developer', 'build', ok=False)
        self.recheck('commit', old, *cases, ok=False)
        self.recheck('commit', current, ok=False)
        (tree/'untracked.txt').write_text('not on commit')
        self.recheck('commit', current, *cases, ok=False)
        (tree/'untracked.txt').unlink()
        self.recheck('commit', current, *cases)
        self.assertEqual(self.changes(), {})
        self.assertEqual(json.loads(self.F('show', 'idea'))['proposal']['sha'], old)
        (tree/'untracked.txt').write_text('not on commit')
        self.F('move', 'fix', 'developer', 'build', ok=False)
        (tree/'untracked.txt').unlink()
        self.F('move', 'fix', 'developer', 'build')

    def test_missing_child_checkout_is_not_a_missing_source(self):
        self.record('pending', '--reason', 'Contract check only')
        tree = self.child()
        tree.rename(tree.with_name('moved-for-test'))
        self.P('status', 'fix', ok=False)

    def test_rejects_escaping_sources_and_reports(self):
        (self.tree/'outside').symlink_to(self.root, target_is_directory=True)
        for src in ['../contract.md','/etc/passwd','.git','outside/contract.md']:
            with self.subTest(src=src):
                self.record('pending', '--reason', 'No fixture', '--source', src, ok=False)
        self.report.unlink()
        self.report.symlink_to(self.root/'contract.md')
        self.record('pending', '--reason', 'No fixture', ok=False)
