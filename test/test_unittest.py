#!/usr/bin/python3

import unittest
import pathlib
import sys
import filecmp
import doctest

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_PATH))

import pygrader.student_repos
from pygrader import Grader, CodeSource

TEST_PATH = ROOT_PATH / "test"
TEST_RESOURCES_PATH = TEST_PATH / "resources"


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(pygrader.student_repos))
    return tests


class TestGithub(unittest.TestCase):
    def test_me(self):
        grader = Grader(
            "test_github",
            "lab1",
            TEST_RESOURCES_PATH / "grades1.csv",
            "lab1",
            10,
            TEST_PATH / "temp",
        )
        grader.set_callback_fcn(lambda **kw: 0)
        grader.set_submission_system_github("master", TEST_RESOURCES_PATH / "github.csv")
        grader.set_other_options(build_only=True)

        grader.run()


class TestLearningSuite(unittest.TestCase):
    def test_me(self):

        grades_path = TEST_RESOURCES_PATH / "grades2.csv"
        grades_path_golden = TEST_RESOURCES_PATH / "grades2_golden.csv"

        grader = Grader(
            "test_learningsuite", "lab1", grades_path, "lab1", (10,), TEST_PATH / "temp"
        )
        grader.set_callback_fcn(self.runner)
        grader.set_submission_system_learning_suite(TEST_RESOURCES_PATH / "submissions.zip")

        # grader = Grader(
        #     name="test_learningsuite",
        #     lab_name="lab1",
        #     points=(10,),
        #     work_path=TEST_PATH / "temp",
        #     code_source=CodeSource.LEARNING_SUITE,
        #     grades_csv_path=grades_path,
        #     grades_col_names=("lab1",),
        #     learning_suite_submissions_zip_path=TEST_RESOURCES_PATH / "submissions.zip",
        #     run_on_milestone=self.runner,
        # )

        grader.run()

        self.assertTrue(filecmp.cmp(grades_path, grades_path_golden))

    def runner(self, **kw):
        print("Modified time:", kw["modified_time"])

        self.assertIn("section", kw)
        self.assertIn("homework_id", kw)
        return 3
