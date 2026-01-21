"""Module to manage each item that is to be graded"""

import csv
import datetime
import sys
from enum import Enum, auto

import numpy as np
import pandas

from .utils import (
    CallbackFailed,
    TermColors,
    print_color,
    error,
    WorkflowHashError,
    verify_workflow_hash,
)
from . import grades_csv
from .deductions import StudentDeductions
from .score_input import get_score, ScoreResult


class ScoreMode(Enum):
    """Enum to specify how scores are determined for a grading item."""

    MANUAL = auto()  # Grader is prompted to enter a score
    DEDUCTIONS = auto()  # Score is computed from max_points minus deductions


class GradeItem:
    """Class to track each item that needs to be graded (ie, each item for which a grading callback
    function will be invoked.  This is used to grade one column from the CSV file.
    """

    def __init__(
        self,
        grader,
        csv_col_name,
        fcn,
        max_points,
        *,
        help_msg=None,
        score_mode=ScoreMode.MANUAL,
        deductions_yaml_path=None,
        fcn_args_dict=None,
    ) -> None:
        self.grader = grader
        self.csv_col_name = csv_col_name
        self.fcn = fcn
        self.max_points = max_points
        self.score_mode = score_mode
        self.help_msg = help_msg
        self.fcn_args_dict = fcn_args_dict if fcn_args_dict is not None else {}

        # If csv_col_name is None, then analysis only
        if csv_col_name is None:
            self.analysis_only = True
        else:
            self.analysis_only = False

        # Load deductions from YAML file (required for DEDUCTIONS mode)
        if score_mode == ScoreMode.DEDUCTIONS:
            if deductions_yaml_path is None:
                raise ValueError(
                    "deductions_yaml_path is required when score_mode is DEDUCTIONS"
                )
            self.student_deductions = StudentDeductions(deductions_yaml_path)
        else:
            self.student_deductions = None

    def run_grading(self, student_grades_df, row, callback_args):
        """Run the grading process for this item"""
        net_ids = grades_csv.get_net_ids(row)
        first_names = grades_csv.get_first_names(row)
        last_names = grades_csv.get_last_names(row)
        num_group_members = len(net_ids)
        concated_names = grades_csv.get_concated_names(row)

        # Add any extra args for the callback function
        if self.fcn_args_dict:
            callback_args.update(self.fcn_args_dict)

        if self.analysis_only:
            num_group_members_need_grade = num_group_members
        else:
            num_group_members_need_grade = self.num_grades_needed(row)

        # variable to flag if build needs to be performed
        # initialize to True as the code must be built at least once
        # (will be false if user chooses to just re-run and not re-build)
        build = True

        if not self.analysis_only and self.num_grades_needed(row) == 0:
            # No one in the group needs grades for this
            print_color(
                TermColors.BLUE,
                "Grade already exists for ",
                self.csv_col_name,
                "(skipping)",
            )
            return

        while True:
            print_color(
                TermColors.BLUE,
                "Running callback function",
                "(" + str(self.fcn.__name__) + ")",
                "to grade",
                str(self.csv_col_name) + ":",
            )

            score = None

            # Build it and run
            try:
                score = self.fcn(
                    **callback_args,
                    csv_col_name=self.csv_col_name,
                    points=self.max_points,
                    build=build and not self.grader.run_only,
                )
            except CallbackFailed as e:
                print_color(TermColors.RED, repr(e))
                break
            except KeyboardInterrupt:
                print("")
            else:
                print_color(TermColors.BLUE, "Callback returned:", score)

            # reset the flag
            build = True

            # If we are only building the code in preparation of grading later,
            # or are performing a dry run,
            # then exit now before asking for a grade
            if self.grader.build_only:
                break
            if self.grader.dry_run_first or self.grader.dry_run_all:
                print_color(
                    TermColors.YELLOW, "'dry_run_*' is set, so no grade will be saved."
                )
                break

            if num_group_members_need_grade < num_group_members:
                print_color(
                    TermColors.YELLOW,
                    "Warning:",
                    num_group_members - num_group_members_need_grade,
                    "group member(s) already have a grade for",
                    self.csv_col_name,
                    "; this grade will be overwritten.",
                )

            # Verify workflow hash if configured
            if self.grader.workflow_hash is not None:
                student_code_path = callback_args.get("student_code_path")
                if student_code_path:
                    workflow_file_path = (
                        student_code_path / ".github" / "workflows" / "submission.yml"
                    )
                    try:
                        verify_workflow_hash(
                            workflow_file_path, self.grader.workflow_hash
                        )
                    except WorkflowHashError as e:
                        print("")
                        print_color(TermColors.RED, "=" * 70)
                        print_color(
                            TermColors.RED,
                            "WARNING: WORKFLOW FILE VERIFICATION FAILED!",
                        )
                        print_color(TermColors.RED, "=" * 70)
                        print_color(TermColors.RED, str(e))
                        print_color(TermColors.RED, "")
                        print_color(
                            TermColors.RED,
                            "This student may have modified the GitHub workflow system.",
                        )
                        print_color(
                            TermColors.RED, "The submission date CANNOT be guaranteed."
                        )
                        print_color(TermColors.RED, "")
                        print_color(
                            TermColors.RED,
                            "Please contact the instructor before grading this student.",
                        )
                        print_color(TermColors.RED, "=" * 70)
                        print("")

            # Display submission date if available
            student_code_path = callback_args.get("student_code_path")
            if student_code_path:
                submission_date_path = student_code_path / ".commitdate"
                if submission_date_path.is_file():
                    try:
                        with open(submission_date_path, encoding="utf-8") as f:
                            submission_time = datetime.datetime.strptime(
                                f.read().strip(),
                                "%a %b %d %H:%M:%S %Z %Y",
                            )
                        print_color(
                            TermColors.BLUE,
                            f"Submitted: {submission_time.strftime('%Y-%m-%d %H:%M:%S')}",
                        )

                        # Calculate late days if due_date is configured
                        if self.grader.due_date is not None:
                            # Check for student-specific due date exception
                            # Use the latest (most generous) exception if multiple group members have them
                            effective_due_date = self.grader.due_date
                            for net_id in net_ids:
                                if net_id in self.grader.due_date_exceptions:
                                    exception_date = self.grader.due_date_exceptions[
                                        net_id
                                    ]
                                    effective_due_date = max(
                                        effective_due_date, exception_date
                                    )

                            has_exception = effective_due_date != self.grader.due_date
                            if has_exception:
                                print_color(
                                    TermColors.YELLOW,
                                    f"Exception due date: {effective_due_date.strftime('%Y-%m-%d %H:%M:%S')}",
                                )

                            if submission_time <= effective_due_date:
                                print_color(TermColors.GREEN, "Status: ON TIME")
                                # Set days_late to 0 (on time) in deductions if using DEDUCTIONS mode
                                if (
                                    self.score_mode == ScoreMode.DEDUCTIONS
                                    and self.student_deductions
                                ):
                                    self.student_deductions.set_days_late(
                                        tuple(net_ids), 0
                                    )
                            else:
                                days_late = np.busday_count(
                                    effective_due_date.date(),
                                    submission_time.date(),
                                )
                                if days_late == 0:
                                    days_late = 1  # Same day but after deadline
                                print_color(
                                    TermColors.RED,
                                    f"Status: LATE ({days_late} business day(s))",
                                )
                                # Store days_late in deductions if using DEDUCTIONS mode
                                if (
                                    self.score_mode == ScoreMode.DEDUCTIONS
                                    and self.student_deductions
                                ):
                                    self.student_deductions.set_days_late(
                                        tuple(net_ids), int(days_late)
                                    )
                    except (ValueError, IOError) as e:
                        print_color(
                            TermColors.YELLOW,
                            f"Could not parse submission date: {e}",
                        )

            if score is None:
                if not self.analysis_only:
                    # Determine score based on score_mode
                    if self.score_mode == ScoreMode.MANUAL:
                        # Prompt the user for a score
                        try:
                            score = get_score(
                                concated_names,
                                self.csv_col_name,
                                self.max_points,
                                help_msg=self.help_msg,
                                allow_rebuild=self.grader.allow_rebuild,
                                allow_rerun=self.grader.allow_rerun,
                            )
                        except KeyboardInterrupt:
                            print_color(TermColors.RED, "\nExiting")
                            sys.exit(0)
                    elif self.score_mode == ScoreMode.DEDUCTIONS:
                        # Prompt with deductions mode - handles everything internally
                        try:
                            score = get_score(
                                concated_names,
                                self.csv_col_name,
                                self.max_points,
                                help_msg=self.help_msg,
                                allow_rebuild=self.grader.allow_rebuild,
                                allow_rerun=self.grader.allow_rerun,
                                student_deductions=self.student_deductions,
                                net_ids=tuple(net_ids),
                            )
                        except KeyboardInterrupt:
                            print_color(TermColors.RED, "\nExiting")
                            sys.exit(0)
            else:
                # If score was returned, validate it
                if self.analysis_only:
                    error(
                        "The grading item was set up as 'analysis only', but the callback returned a score."
                    )

            if self.analysis_only:
                break

            if score == ScoreResult.SKIP:
                break
            if score == ScoreResult.REBUILD:
                continue
            if score == ScoreResult.RERUN:
                # run again, but don't build
                build = False
                continue

            # Record score
            for _, _, net_id in zip(first_names, last_names, net_ids):
                row_idx = grades_csv.find_idx_for_netid(student_grades_df, net_id)

                student_grades_df.at[row_idx, self.csv_col_name] = score

            student_grades_df.to_csv(
                str(self.grader.grades_csv_path),
                index=False,
                quoting=csv.QUOTE_ALL,
            )
            break

    def num_grades_needed(self, row):
        """Return the number of group members who need a grade for this column."""
        empty_cnt = 0
        for grade in row[self.csv_col_name]:
            if pandas.isnull(grade):
                empty_cnt += 1
        return empty_cnt
