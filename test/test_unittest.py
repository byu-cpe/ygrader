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
            lab_name="github_test",
            grades_csv_path=TEST_RESOURCES_PATH / "grades1.csv",
            work_path=TEST_PATH / "temp",
        )
        grader.add_item_to_grade("lab1", self.runner, 10)
        grader.add_item_to_grade("lab1m2", self.runner, 20)
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
            lab_name="learningsuite_test",
            grades_csv_path=grades_path,
            work_path=TEST_PATH / "temp",
        )
        grader.add_item_to_grade(
            csv_col_names="lab1",
            grading_fcn=self.runner,
            max_points=(10,),
        )
        grader.set_submission_system_learning_suite(TEST_RESOURCES_PATH / "submissions.zip")
        grader.run()

        self.assertTrue(filecmp.cmp(grades_path, grades_path_golden))

    def runner(self, student_code_path, **kw):
        self.assertIn("section", kw)
        self.assertIn("homework_id", kw)
        if (student_code_path / "file_1.txt").is_file() and (
            student_code_path / "file_2.txt"
        ).is_file():
            return 3
        else:
            return 0

    def test_groups(self):
        grader = Grader(
            "groups_test",
            TEST_RESOURCES_PATH / "grades3.csv",
            work_path=TEST_PATH / "temp",
        )
        grader.add_item_to_grade(
            csv_col_names="l1",
            grading_fcn=self.group_grader_1,
        )
        grader.add_item_to_grade(
            ("l2", "l3"), self.group_grader_2, help_msg=("rubric message 1", "rubric message 2")
        )
        grader.set_submission_system_learning_suite(TEST_RESOURCES_PATH / "submissions2.zip")
        grader.set_learning_suite_groups(TEST_RESOURCES_PATH / "groups3.csv")
        grader.run()

    def group_grader_1(self, **kw):
        return 1.5

    def group_grader_2(self, **kw):
        return (2, 3.0)
