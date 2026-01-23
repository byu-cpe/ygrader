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
    time.sleep(1)


def run_on_milestone(**kwargs):
    print("run_on_milestone")
    time.sleep(1)


def test_me():
    grader = Grader(
        lab_name="lab1",
        grades_csv_path=TEST_RESOURCES_PATH / "grades1.csv",
        work_path=TEST_PATH / "temp",
    )
    grader.add_item_to_grade(
        "lab1",
        run_on_milestone,
        10,
    )
    grader.add_item_to_grade(
        "lab1m2",
        run_on_milestone,
    )
    grader.set_submission_system_learning_suite(TEST_RESOURCES_PATH / "submissions.zip")
    grader.set_other_options(prep_fcn=run_on_lab)
    grader.run()


if __name__ == "__main__":
    test_me()
