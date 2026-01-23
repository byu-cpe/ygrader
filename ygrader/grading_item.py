"""Module to manage each item that is to be graded"""

import datetime
import sys

from .utils import (
    CallbackFailed,
    TermColors,
    print_color,
    WorkflowHashError,
    verify_workflow_hash,
)
from . import grades_csv
from .deductions import StudentDeductions
from .score_input import get_score, ScoreResult


class GradeItem:
    """Class to track each item that needs to be graded (ie, each item for which a grading callback
    function will be invoked.  This is used to grade one column from the CSV file.
    """

    def __init__(
        self,
        grader,
        item_name,
        *,
        fcn,
        max_points,
        deductions_yaml_path,
        fcn_args_dict=None,
    ) -> None:
        self.grader = grader
        self.item_name = item_name
        self.fcn = fcn
        self.max_points = max_points
        self.fcn_args_dict = fcn_args_dict if fcn_args_dict is not None else {}
        self.student_deductions = StudentDeductions(deductions_yaml_path)

    def run_grading(self, _student_grades_df, row, callback_args):
        """Run the grading process for this item"""
        net_ids = grades_csv.get_net_ids(row)
        num_group_members = len(net_ids)
        concated_names = grades_csv.get_concated_names(row)
        callback_args["item_name"] = self.item_name

        # Add any extra args for the callback function
        if self.fcn_args_dict:
            callback_args.update(self.fcn_args_dict)

        # Check if student is already in the deductions file
        num_group_members_need_grade = self.num_grades_needed_deductions(net_ids)

        # variable to flag if build needs to be performed
        # initialize to True as the code must be built at least once
        # (will be false if user chooses to just re-run and not re-build)
        build = True

        if num_group_members_need_grade == 0:
            # No one in the group needs grades for this
            print_color(
                TermColors.BLUE,
                "Grade already exists for this item",
                "(skipping)",
            )
            return

        while True:
            print_color(
                TermColors.BLUE,
                "Running callback function",
                "(" + str(self.fcn.__name__) + ")",
                "to grade item:",
            )

            callback_result = None

            # Build it and run
            try:
                callback_result = self.fcn(
                    **callback_args,
                    points=self.max_points,
                    build=build and not self.grader.run_only,
                )
            except CallbackFailed as e:
                print_color(TermColors.RED, repr(e))
                break
            except KeyboardInterrupt:
                print("")

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
                    "group member(s) already have a grade for this item",
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

            # Display submission date if available and store for later late calculation
            student_code_path = callback_args.get("student_code_path")
            # Store submission time but don't save yet - will be saved only after successful grading
            pending_submit_time = None
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
                        # Store as ISO format for later late calculation
                        pending_submit_time = submission_time.isoformat()
                    except (ValueError, IOError) as e:
                        print_color(
                            TermColors.YELLOW,
                            f"Could not parse submission date: {e}",
                        )

            # Process callback result:
            # - None: interactive mode (prompt for deductions)
            # - List of (str, int) tuples: automatic deductions to apply
            if callback_result is not None:
                # Callback returned deductions to apply automatically
                if isinstance(callback_result, list):
                    for deduction_desc, deduction_points in callback_result:
                        # Find or create the deduction type
                        deduction_id = (
                            self.student_deductions.find_or_create_deduction_type(
                                deduction_desc, deduction_points
                            )
                        )
                        # Apply to this student
                        self.student_deductions.apply_deduction_to_student(
                            tuple(net_ids), deduction_id
                        )
                        print_color(
                            TermColors.BLUE,
                            f"Applied deduction: {deduction_desc} (-{deduction_points})",
                        )
                    # Save submit_time now that grading succeeded
                    if pending_submit_time is not None:
                        self.student_deductions.set_submit_time(
                            tuple(net_ids), pending_submit_time
                        )
                    # Ensure student is in the deductions file
                    self.student_deductions.ensure_student_in_file(tuple(net_ids))
                    break

                print_color(
                    TermColors.RED,
                    f"Invalid callback return type: {type(callback_result)}. Expected None or list of (str, int) tuples.",
                )
                # Don't mark student as graded - just skip to next student
                break

            # callback_result is None - interactive mode
            # Prompt with deductions mode - handles everything internally
            try:
                score = get_score(
                    concated_names,
                    self.max_points,
                    allow_rebuild=self.grader.allow_rebuild,
                    allow_rerun=self.grader.allow_rerun,
                    student_deductions=self.student_deductions,
                    net_ids=tuple(net_ids),
                )
            except KeyboardInterrupt:
                print_color(TermColors.RED, "\nExiting")
                sys.exit(0)

            if score == ScoreResult.SKIP:
                break
            if score == ScoreResult.REBUILD:
                continue
            if score == ScoreResult.RERUN:
                # run again, but don't build
                build = False
                continue

            # Record score - save submit_time and ensure the student is in the deductions file
            # (even if they have no deductions, to indicate they were graded)
            if pending_submit_time is not None:
                self.student_deductions.set_submit_time(tuple(net_ids), pending_submit_time)
            self.student_deductions.ensure_student_in_file(tuple(net_ids))
            break

    def num_grades_needed_deductions(self, net_ids):
        """Return the number of group members who need a grade.

        A student needs grading if they're not in the deductions file.
        """
        if self.student_deductions.is_student_graded(tuple(net_ids)):
            return 0
        return len(net_ids)
