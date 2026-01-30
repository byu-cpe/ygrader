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
from .score_input import get_score, MenuCommand


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
        self.names_by_netid = (
            self._build_names_lookup()
        )  # net_id -> (first_name, last_name)

    def _build_names_lookup(self):
        """Build a lookup dictionary from net_id to (first_name, last_name) from the class list CSV."""
        # Import pandas here to avoid circular import and since it's already imported in grader.py
        import pandas  # pylint: disable=import-outside-toplevel

        names_by_netid = {}
        try:
            df = pandas.read_csv(self.grader.class_list_csv_path)
            for _, row in df.iterrows():
                if "Net ID" in row and "First Name" in row and "Last Name" in row:
                    net_id = row["Net ID"]
                    first_name = row["First Name"]
                    last_name = row["Last Name"]
                    if (
                        pandas.notna(net_id)
                        and pandas.notna(first_name)
                        and pandas.notna(last_name)
                    ):
                        names_by_netid[net_id] = (first_name, last_name)
        except (FileNotFoundError, pandas.errors.EmptyDataError, KeyError):
            pass  # If we can't read the CSV, just use an empty dict
        return names_by_netid

    def run_grading(self, _student_grades_df, row, callback_args):
        """Run the grading process for this item.

        Returns:
            True if user requested to go back and regrade the previous student,
            False otherwise.
        """
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
            return False

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
            workflow_errors = []
            student_code_path = callback_args.get("student_code_path")
            if self.grader.workflow_hash is not None and student_code_path:
                workflow_file_path = (
                    student_code_path / ".github" / "workflows" / "submission.yml"
                )
                try:
                    verify_workflow_hash(workflow_file_path, self.grader.workflow_hash)
                except WorkflowHashError as e:
                    workflow_errors.append(f"Workflow hash mismatch: {e}")

            # Display submission date if available and store for later late calculation
            # Store submission time but don't save yet - will be saved only after successful grading
            pending_submit_time = None
            if student_code_path:
                submission_date_path = student_code_path / ".commitdate"
                if submission_date_path.is_file():
                    try:
                        with open(submission_date_path, encoding="utf-8") as f:
                            date_str = f.read().strip()
                        # Expected format from workflow: "Sun Jan 12 21:51:14 MST 2026"
                        submission_time = datetime.datetime.strptime(
                            date_str,
                            "%a %b %d %H:%M:%S %Z %Y",
                        )
                        print_color(
                            TermColors.BLUE,
                            f"Submitted: {submission_time.strftime('%Y-%m-%d %H:%M:%S')}",
                        )
                        # Store as ISO format for later late calculation
                        pending_submit_time = submission_time.isoformat()
                    except (ValueError, IOError) as e:
                        workflow_errors.append(f"Submission date parsing failed: {e}")

            # Print unified warning if any workflow-related errors occurred
            if workflow_errors:
                print("")
                print_color(TermColors.RED, "=" * 70)
                print_color(
                    TermColors.RED,
                    "WARNING: WORKFLOW VERIFICATION FAILED!",
                )
                print_color(TermColors.RED, "=" * 70)
                for err in workflow_errors:
                    print_color(TermColors.RED, f"  - {err}")
                print_color(TermColors.RED, "")
                print_color(
                    TermColors.RED,
                    "This student may have modified the GitHub workflow system.",
                )
                print_color(TermColors.RED, "The submission date CANNOT be guaranteed.")
                print_color(TermColors.RED, "")
                print_color(
                    TermColors.RED,
                    "Please contact the instructor before grading this student.",
                )
                print_color(TermColors.RED, "=" * 70)
                print("")

                # Ask for confirmation before grading
                while True:
                    response = (
                        input("Do you want to grade this student anyway? [y/n]: ")
                        .strip()
                        .lower()
                    )
                    if response in ("y", "yes"):
                        break
                    if response in ("n", "no"):
                        print_color(TermColors.BLUE, "Skipping student")
                        return False
                    print("Please enter 'y' or 'n'")

            # Process callback result:
            # - None: interactive mode (prompt for deductions)
            # - List of (str, int) tuples: automatic deductions to apply
            if callback_result is not None:
                # Callback returned deductions to apply automatically
                if isinstance(callback_result, list):
                    for deduction_desc, deduction_points in callback_result:
                        if deduction_points < 0:
                            raise ValueError(
                                f"Deduction points must be non-negative, got {deduction_points} "
                                f"for '{deduction_desc}'"
                            )
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
                    # (may be None if no .commitdate file exists)
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
                    last_graded_net_ids=self.grader.last_graded_net_ids,
                    names_by_netid=self.names_by_netid,
                    all_items=self.grader.items,
                )
            except KeyboardInterrupt:
                print_color(TermColors.RED, "\nExiting")
                sys.exit(0)

            if score == MenuCommand.SKIP:
                return False
            if score == MenuCommand.BUILD:
                continue
            if score == MenuCommand.RERUN:
                # run again, but don't build
                build = False
                continue
            if score == MenuCommand.EXIT:
                print_color(TermColors.BLUE, "Exiting grader")
                sys.exit(0)
            if score == MenuCommand.UNDO:
                # Undo the last graded student and signal to go back
                if self.grader.last_graded_net_ids is not None:
                    # Clear deductions for ALL items for the last graded student
                    for item in self.grader.items:
                        item.student_deductions.clear_student_deductions(
                            self.grader.last_graded_net_ids
                        )
                    # Also clear any partial grades for the CURRENT student
                    # so they start fresh when we come back to them
                    for item in self.grader.items:
                        item.student_deductions.clear_student_deductions(tuple(net_ids))
                    print_color(
                        TermColors.GREEN,
                        f"Undid grade for {', '.join(self.grader.last_graded_net_ids)} - going back to regrade",
                    )
                    print_color(
                        TermColors.GREEN,
                        f"Also cleared partial grades for {', '.join(net_ids)}",
                    )
                    return True  # Signal to go back to previous student
                continue

            # Record score - save submit_time and ensure the student is in the deductions file
            # (even if they have no deductions, to indicate they were graded)
            # submit_time may be None if no .commitdate file exists
            self.student_deductions.set_submit_time(tuple(net_ids), pending_submit_time)
            self.student_deductions.ensure_student_in_file(tuple(net_ids))
            return False  # Normal completion

        # If we got here via break (CallbackFailed, build_only, dry_run, etc.)
        return False

    def num_grades_needed_deductions(self, net_ids):
        """Return the number of group members who need a grade.

        A student needs grading if they're not in the deductions file.
        """
        if self.student_deductions.is_student_graded(tuple(net_ids)):
            return 0
        return len(net_ids)
