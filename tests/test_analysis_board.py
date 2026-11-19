import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/factory/skills/factory/scripts'))
from board import render


class Card(HTMLParser):
    def __init__(self, **job):
        super().__init__()
        self.in_card = False
        self.in_details = False
        self.summary_text = []
        self.detail_text = []
        self.tags = set()
        self.feed(render([dict({'id': 'issue', 'title': 'Lookup', 'stage': 'ok'}, **job)], 'Example'))

    def handle_starttag(self, tag, attrs):
        if tag == 'article':
            self.in_card = True
        if tag == 'details':
            self.in_details = True
        if self.in_card:
            self.tags.add(tag)

    def handle_endtag(self, tag):
        if tag == 'article':
            self.in_card = False
        if tag == 'details':
            self.in_details = False

    def handle_data(self, data):
        if self.in_card:
            target = self.detail_text if self.in_details else self.summary_text
            target.append(data)


class AnalysisBoard(unittest.TestCase):
    def test_pending_proposal_visible_on_card_before_and_after_intake(self):
        pending = 'Proposta da verificare'
        self.assertIn(pending, Card(stage='design', proposal_requested=True).summary_text)
        recorded = Card(proposal={'status': 'pending', 'reason': 'Manca un dato autorizzato'})
        self.assertIn(pending, recorded.summary_text)
        self.assertIn('Manca un dato autorizzato', recorded.detail_text)
        self.assertNotIn(pending, Card(design_only=True).summary_text)

    def test_verified_evidence_scoped_to_fixture_or_exact_revision(self):
        sha = 'a' * 40
        for status, expected in [('fixture', 'Verificata su copia temporanea'),
                                  ('commit', 'Verificata sul commit ' + sha)]:
            with self.subTest(status=status):
                proof = {'status': status, 'case': 'Caso <img> passato', 'control': 'Chiave assente',
                         'sha': sha if status == 'commit' else '', 'reason': 'Solo dati sintetici',
                         'sources': {'private-vault/note.md': 'digest'},
                         'external': ['private-online-reference']}
                card = Card(proposal=proof)
                self.assertIn(expected, card.summary_text)
                self.assertIn('OK', card.summary_text)
                for value in (proof['case'], proof['control'], proof['reason']):
                    self.assertIn(value, card.detail_text)
                self.assertNotIn('img', card.tags)
                for value in ('private-vault', 'private-online-reference'):
                    self.assertNotIn(value, ' '.join(card.summary_text + card.detail_text))

    def test_open_question_and_answer_remain_paired_after_resume(self):
        first = {'key': 'aziende', 'ref': 'decision-1', 'question': 'Confermare il formato <i>?',
                 'answer': 'Solo v2 <b>', 'from_stage': 'design'}
        second = {'key': 'import', 'ref': 'decision-2', 'question': 'Includere import?',
                  'from_stage': 'design'}
        waiting = dict(stage='feedback', decisions=[first, second], decision_wait=second['ref'])
        card = Card(**waiting)
        self.assertIn('Decisione richiesta', card.summary_text)
        self.assertIn(second['question'], card.summary_text)
        self.assertNotIn('Solo v2 <b>', card.summary_text)
        for value in [first['question'], first['answer'], second['question']]:
            self.assertIn(value, card.detail_text)
        self.assertNotIn('i', card.tags)
        self.assertNotIn('b', card.tags)
        second['answer'] = 'Sì'
        self.assertIn('Risposta ricevuta', Card(**waiting).summary_text)
        resumed = Card(stage='design', decisions=[first, second])
        self.assertIn('Progettazione', resumed.summary_text)
        self.assertIn(second['answer'], resumed.detail_text)
        delivery = Card(stage='feedback', decisions=[first, second],
                        delivery={'status': 'waiting', 'action': 'merge'})
        self.assertIn('Approvazione merge', delivery.summary_text)
        self.assertNotIn('Decisione richiesta', delivery.summary_text)
