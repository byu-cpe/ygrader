#!/usr/bin/python3

import unittest
import pathlib
import sys
import filecmp
import doctest

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_PATH))

import ygrader.student_repos
from ygrader import Grader, CodeSource

TEST_PATH = ROOT_PATH / "test"
TEST_RESOURCES_PATH = TEST_PATH / "resources"


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(ygrader.student_repos))
    return tests


class TestGithub(unittest.TestCase):
    def test_me(self):
        grades_path = TEST_RESOURCES_PATH / "grades1.csv"
        grades_path_golden = TEST_RESOURCES_PATH / "grades1_golden.csv"

        grader = Grader(
            lab_name="lab1",
            grades_csv_path=TEST_RESOURCES_PATH / "grades1.csv",
            grades_col_name=("lab1", "lab1m2"),
            points=(10, 20),
            work_path=TEST_PATH / "temp",
        )
        grader.set_callback_fcn(self.runner)
        grader.set_submission_system_github(
            "main", TEST_RESOURCES_PATH / "github.csv", use_https=True
        )

        grader.run()

        self.assertTrue(filecmp.cmp(grades_path, grades_path_golden))

    def runner(self, **kw):
        return kw["points"]


class TestLearningSuite(unittest.TestCase):
    def test_me(self):

        grades_path = TEST_RESOURCES_PATH / "grades2.csv"
        grades_path_golden = TEST_RESOURCES_PATH / "grades2_golden.csv"

        grader = Grader(
            lab_name="lab1",
            grades_csv_path=grades_path,
            grades_col_name="lab1",
            points=(10,),
            work_path=TEST_PATH / "temp",
        )
        grader.set_callback_fcn(self.runner)
        grader.set_submission_system_learning_suite(TEST_RESOURCES_PATH / "submissions.zip")
        grader.run()

        self.assertTrue(filecmp.cmp(grades_path, grades_path_golden))

    def runner(self, **kw):
        print("Modified time:", kw["modified_time"])

        self.assertIn("section", kw)
        self.assertIn("homework_id", kw)
        return 3
