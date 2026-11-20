import copy
import json

from django.db import connection
from django.test import TestCase

from ctf.contract import CONTRACT_PATH, load_contract, missing_from_database


class ContractTests(TestCase):
    def test_contract_satisfied_by_database(self):
        self.assertEqual(missing_from_database(load_contract()), [])

    def test_contract_covers_required_tables(self):
        tables = load_contract()["tables"]
        for t in ("ctf_solve", "ctf_submission", "ctf_challenge", "ctf_membership",
                  "ctf_practicegroup", "accounts_user"):
            self.assertIn(t, tables)
        self.assertLessEqual({"flag_hmac", "points", "pub_date", "slug", "id"},
                             set(tables["ctf_challenge"]))
        self.assertLessEqual({"id", "handle"}, set(tables["accounts_user"]))
        self.assertNotIn("text", " ".join(tables["ctf_submission"]))

    def test_file_is_valid_json(self):
        json.loads(CONTRACT_PATH.read_text())

    def test_renamed_column_fails(self):
        doctored = copy.deepcopy(load_contract())
        doctored["tables"]["ctf_solve"].append("solved_when")
        problems = missing_from_database(doctored)
        self.assertEqual(problems, ["ctf_solve.solved_when"])

    def test_missing_table_fails(self):
        doctored = {"version": 1, "tables": {"ctf_nope": ["id"]}}
        self.assertEqual(missing_from_database(doctored), ["ctf_nope (table)"])
