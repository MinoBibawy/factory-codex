import concurrent.futures
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/factory/skills/factory/scripts'


class ProjectDecisions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        self.run_cli('add', 'item', 'Catalog proposal', '--design-only')
        self.run_cli('claim', 'item', 'worker')

    def run_cli(self, *args, script='factory', ok=True):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPTS / f'{script}.py'), *args],
                              cwd=self.project, capture_output=True, text=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        return proc.stderr

    def ask(self, key='catalog', text='Keep leading zeroes?'):
        return self.run_cli('ask', 'item', 'worker', key, text)

    def answer(self, ref, text, **opts):
        return self.run_cli('answer', 'item', 'worker', ref, text, **opts)

    def test_restart_exact_retries_and_stale_answers(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            first, duplicate = pool.map(lambda _: self.ask(), range(2))
        self.assertEqual(first, duplicate)
        ref = first['decisions'][0]['ref']
        self.assertEqual(first['decision_wait'], ref)
        resume = self.run_cli('item', script='resume')
        self.assertEqual(resume['action'], 'await_answer')
        self.assertEqual(resume['decision']['question'], 'Keep leading zeroes?')
        self.run_cli('move', 'item', 'worker', 'design', '--note', 'yes', ok=False)
        self.answer('wrong-reference', 'yes', ok=False)
        self.run_cli('answer', 'item', 'another-worker', ref, 'yes', ok=False)
        self.run_cli('ask', 'item', 'worker', 'catalog', 'A different question?', ok=False)
        self.run_cli('ask', 'item', 'worker', 'other', 'A parallel question?', ok=False)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            answered, retry = pool.map(lambda _: self.answer(ref, 'Keep as text.'), range(2))
        self.assertEqual(answered, retry)
        self.assertEqual(answered['stage'], 'design')
        fresh = self.run_cli('item', script='resume')
        self.assertEqual(fresh['action'], 'design')
        self.assertEqual(fresh['decision']['answer'], 'Keep as text.')
        self.assertNotIn('delivery', answered)
        self.assertNotIn('decision_wait', answered)
        self.assertEqual(self.ask(), answered)
        self.answer(ref, 'Cast to integer.', ok=False)
        second = self.ask('wire', 'Use a string on the wire?')
        self.assertNotEqual(ref, second['decision_wait'])
        self.answer(ref, 'Keep as text.', ok=False)
        self.assertEqual(self.run_cli('show', 'item'), second)
        self.assertEqual(self.answer(second['decision_wait'], 'Yes.')['decisions'][0]['answer'],
                         'Keep as text.')

    def test_capacity_preserves_answer_until_project_slot_is_free(self):
        ref = self.ask()['decision_wait']
        self.run_cli('add', 'other', 'Another local job')
        self.run_cli('claim', 'other', 'worker2')
        self.run_cli('intake', 'other', 'worker2', 'accept', '--agent', 'triage',
                     '--skill', 'factory-analysis', '--evidence', 'Case checked')
        self.run_cli('move', 'other', 'worker2', 'build')
        blocked = self.answer(ref, 'Use text.')
        self.assertEqual(blocked['stage'], 'feedback')
        self.assertEqual(blocked['decisions'][-1]['answer'], 'Use text.')
        self.assertEqual(self.answer(ref, 'Use text.'), blocked)
        self.assertEqual(self.run_cli('item', script='resume')['action'], 'resume_decision')
        self.run_cli('move', 'other', 'worker2', 'ko', '--note', 'Job cancelled')
        self.assertEqual(self.answer(ref, 'Use text.')['stage'], 'design')

    def test_retries_cannot_answer_a_different_job_or_authorize_delivery(self):
        first = self.ask()['decision_wait']
        self.run_cli('add', 'other', 'Another job')
        self.run_cli('claim', 'other', 'other-worker')
        other = self.run_cli('ask', 'other', 'other-worker', 'catalog', 'Keep leading zeroes?')
        self.assertNotEqual(first, other['decision_wait'])
        self.run_cli('answer', 'other', 'other-worker', first, 'yes', ok=False)
        self.run_cli('move', 'item', 'worker', 'ko', '--note', 'User cancelled')
        self.answer(first, 'yes', ok=False)
        self.assertNotIn('decision_wait', self.run_cli('show', 'item'))
        # A prior-version queue can already be waiting for publication approval.
        queue = self.project / '.factory' / 'queue.json'
        data = json.loads(queue.read_text())
        job = data['jobs']['other']
        job.pop('decision_wait')
        job.pop('decisions')
        job.update(feedback_from='ready', delivery={'action': 'push', 'status': 'waiting'})
        queue.write_text(json.dumps(data))
        self.run_cli('ask', 'other', 'other-worker', 'publish', 'Approve?', ok=False)
        self.run_cli('answer', 'other', 'other-worker', 'irrelevant', 'yes', ok=False)
        self.assertEqual(self.run_cli('show', 'other')['delivery'], job['delivery'])
