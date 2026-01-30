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
TEST_OUTPUT_PATH = TEST_PATH / "grades"


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(ygrader.student_repos))
    return tests


class TestGithub(unittest.TestCase):
    def test_me(self):
        class_list_csv_path = TEST_RESOURCES_PATH / "class_list_1.csv"
        deductions1_golden_path = TEST_RESOURCES_PATH / "deductions1_golden.yaml"
        deductions2_golden_path = TEST_RESOURCES_PATH / "deductions2_golden.yaml"
        deductions1_yaml_path = TEST_OUTPUT_PATH / "deductions1.yaml"
        deductions2_yaml_path = TEST_OUTPUT_PATH / "deductions2.yaml"

        grader = Grader(
            lab_name="github_test",
            class_list_csv_path=class_list_csv_path,
            work_path=TEST_PATH / "temp_github",
        )
        grader.add_item_to_grade(
            "lab1",
            self.runner,
            max_points=10,
            deductions_yaml_path=deductions1_yaml_path,
        )
        grader.add_item_to_grade(
            "lab1m2",
            self.runner,
            max_points=20,
            deductions_yaml_path=deductions2_yaml_path,
        )
        grader.set_submission_system_github(
            "main", TEST_RESOURCES_PATH / "github.csv", use_https=True
        )
        grader.set_other_options(show_completion_menu=False)
        grader.run()

        self.assertTrue(filecmp.cmp(deductions1_yaml_path, deductions1_golden_path))
        self.assertTrue(filecmp.cmp(deductions2_yaml_path, deductions2_golden_path))

    def runner(self, **kw):
        if kw["item_name"] == "lab1m2":
            return [("New feedback", 2)]
        return []


class TestLearningSuite(unittest.TestCase):
    def test_me(self):
        class_list_csv_path = TEST_RESOURCES_PATH / "class_list_2.csv"
        deductions_path = TEST_OUTPUT_PATH / "learningsuite_deductions.yaml"
        deductions_golden_path = (
            TEST_RESOURCES_PATH / "learningsuite_deductions_golden.yaml"
        )

        grader = Grader(
            lab_name="learningsuite_test",
            class_list_csv_path=class_list_csv_path,
            work_path=TEST_PATH / "temp_learningsuite",
        )
        grader.add_item_to_grade(
            item_name="lab1",
            grading_fcn=self.runner,
            deductions_yaml_path=deductions_path,
            max_points=10,
        )
        grader.set_submission_system_learning_suite(
            TEST_RESOURCES_PATH / "submissions.zip"
        )
        grader.set_other_options(show_completion_menu=False)
        grader.run()

        self.assertTrue(filecmp.cmp(deductions_path, deductions_golden_path))

    def runner(self, student_code_path, **kw):
        self.assertIn("section", kw)
        self.assertIn("homework_id", kw)
        if (student_code_path / "file_1.txt").is_file() and (
            student_code_path / "file_2.txt"
        ).is_file():
            return []
        else:
            return [("Missing files", 10)]

    def test_groups(self):
        class_list_csv_path = TEST_RESOURCES_PATH / "class_list_3.csv"
        deductions1_path = TEST_OUTPUT_PATH / "groups_l1.yaml"
        deductions2_path = TEST_OUTPUT_PATH / "groups_l2.yaml"
        deductions3_path = TEST_OUTPUT_PATH / "groups_l3.yaml"
        deductions1_golden_path = TEST_RESOURCES_PATH / "groups_l1_golden.yaml"
        deductions2_golden_path = TEST_RESOURCES_PATH / "groups_l2_golden.yaml"
        deductions3_golden_path = TEST_RESOURCES_PATH / "groups_l3_golden.yaml"

        grader = Grader(
            "groups_test",
            class_list_csv_path=class_list_csv_path,
            work_path=TEST_PATH / "temp_groups",
        )
        grader.add_item_to_grade(
            item_name="l1",
            grading_fcn=self.group_grader_1,
            deductions_yaml_path=deductions1_path,
            max_points=10,
        )
        grader.add_item_to_grade(
            item_name="l2",
            grading_fcn=self.group_grader_2,
            deductions_yaml_path=deductions2_path,
            max_points=10,
        )
        grader.set_submission_system_learning_suite(
            TEST_RESOURCES_PATH / "submissions2.zip"
        )
        grader.set_learning_suite_groups(TEST_RESOURCES_PATH / "groups3.csv")
        grader.set_other_options(show_completion_menu=False)
        grader.run()

        self.assertTrue(filecmp.cmp(deductions1_path, deductions1_golden_path))
        self.assertTrue(filecmp.cmp(deductions2_path, deductions2_golden_path))

    def group_grader_1(self, **kw):
        return []

    def group_grader_2(self, **kw):
        return [("Did not follow instructions", 5)]
