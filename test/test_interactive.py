#!/usr/bin/python3

import unittest
import pathlib
import sys
import time


ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_PATH))

from ygrader import Grader, CodeSource

TEST_PATH = ROOT_PATH / "test"
TEST_RESOURCES_PATH = TEST_PATH / "resources"


def run_on_lab(**kwargs):
    print("run_on_lab")
    time.sleep(5)


def run_on_milestone(**kwargs):
    print("run_on_milestone")
    time.sleep(5)


def test_me():
    grader = Grader(
        name="test_learningsuite",
        lab_name="lab1",
        points=(10, 20),
        work_path=TEST_PATH / "temp",
        code_source=CodeSource.LEARNING_SUITE,
        grades_csv_path=TEST_RESOURCES_PATH / "grades1.csv",
        grades_col_names=("lab1", "lab1m2"),
        learning_suite_submissions_zip_path=TEST_RESOURCES_PATH / "submissions.zip",
        help_msg=["This is a long string\nWith lots of advice\nFor TAs", "msg2"],
        run_on_lab=run_on_lab,
        run_on_milestone=run_on_milestone,
    )
    grader.run()


if __name__ == "__main__":
    test_me()
