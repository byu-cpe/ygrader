""" Module to manage each item that is to be graded"""


import csv
import json
import shutil
import sys

import pandas

from .utils import CallbackFailed, TermColors, print_color, error
from . import grades_csv, utils


class GradeItem:
    """Class to track each item that needs to be graded (ie, each item for which a grading callback
    function will be invoked.  This may be used to grade one or more columns from the CSV file."""

    def __init__(
        self, grader, csv_col_names, fcn, max_points, feedback_filename, feedback_col_name, help_msg
    ) -> None:
        self.grader = grader
        self.csv_col_names = csv_col_names
        self.fcn = fcn
        self.max_points = max_points
        self.feedback_filename = feedback_filename
        self.feedback_col_name = feedback_col_name
        self.feedback_enabled = self.feedback_filename or self.feedback_col_name
        self.help_msg = help_msg

        # If any csv_col_names is None, then analysis only
        if None in csv_col_names:
            self.analysis_only = True
            assert len(csv_col_names) == 1
        else:
            self.analysis_only = False

        # Feedback comments
        self.feedback_list_path = self.grader.work_path / (str(csv_col_names) + ".json")
        self.feedback_list = []
        if self.feedback_list_path.is_file():
            with open(self.feedback_list_path, encoding="utf-8") as f:
                self.feedback_list = json.load(f)

        # Feeback file directory
        if self.feedback_filename:
            self.feedback_dir_path = (
                grader.grades_csv_path.parent / "feedback" / self.feedback_filename
            )
            self.feedback_zip_path = (
                grader.grades_csv_path.parent / "feedback" / (self.feedback_filename + ".zip")
            )
            self.feedback_dir_path.mkdir(exist_ok=True, parents=True)

    def run_grading(self, student_grades_df, row, callback_args):
        """Run the grading process for this item"""
        net_ids = grades_csv.get_net_ids(row)
        first_names = grades_csv.get_first_names(row)
        last_names = grades_csv.get_last_names(row)
        num_group_members = len(net_ids)
        concated_names = grades_csv.get_concated_names(row)

        if self.analysis_only:
            num_group_members_need_grade_per_col = (num_group_members,)
        else:
            num_group_members_need_grade_per_col = self.num_grades_needed(row)

        # variable to flag if build needs to be performed
        # initialize to True as the code must be built at least once
        # (will be false if user chooses to just re-run and not re-build)
        build = True

        if not self.analysis_only and sum(self.num_grades_needed(row)) == 0:
            # No one in the group needs grades for this
            print_color(
                TermColors.BLUE,
                "Grade already exists for ",
                self.csv_col_names,
                "(skipping)",
            )
            return

        while True:
            print_color(
                TermColors.BLUE,
                "Running callback function",
                "(" + str(self.fcn.__name__) + ")",
                "to grade",
                str(self.csv_col_names) + ":",
            )

            scores = None

            # Build it and run
            try:
                scores = self.fcn(
                    **callback_args,
                    csv_col_names=self.csv_col_names,
                    points=self.max_points,
                    build=build and not self.grader.run_only,
                )
            except CallbackFailed as e:
                print_color(TermColors.RED, repr(e))
                break
            except KeyboardInterrupt:
                print("")
            else:
                print_color(TermColors.BLUE, "Callback returned:", scores)

            # reset the flag
            build = True

            # If we are only building the code in preparation of grading later,
            # or are performing a dry run,
            # then exit now before asking for a grade
            if self.grader.build_only:
                break
            if self.grader.dry_run_first or self.grader.dry_run_all:
                print_color(TermColors.YELLOW, "'dry_run_*' is set, so no grade will be saved.")
                break

            for i, col in enumerate(self.csv_col_names):
                if num_group_members_need_grade_per_col[i] < num_group_members:
                    print_color(
                        TermColors.YELLOW,
                        "Warning:",
                        num_group_members - num_group_members_need_grade_per_col[i],
                        "group member(s) already have a grade for",
                        col,
                        "; this grade will be overwritten.",
                    )

            if scores is None:
                if not self.analysis_only:
                    # If no score was returned by the callback function, prompt the user for a score.
                    try:
                        scores, feedback = self._get_scores(concated_names)
                    except KeyboardInterrupt:
                        print_color(TermColors.RED, "\nExiting")
                        sys.exit(0)
            else:
                # If score(s) were returned, make sure the length matches the number of columns to be graded
                if self.analysis_only:
                    error(
                        "The grading item was set up as 'analysis only', but the callback returned a score."
                    )

                scores = utils.ensure_tuple(scores)
                expected_lenth = len(self.csv_col_names)
                if self.feedback_enabled:
                    expected_lenth += 1
                if len(scores) != expected_lenth:
                    error(
                        "The callback should be grading",
                        len(self.csv_col_names),
                        "column(s)",
                        "(" + str(self.csv_col_names) + "),",
                        "but",
                        len(scores),
                        "values were returned.",
                        "Since feedback is enabled, you should return one extra item that is the feedback, which can be an empty string for no feedback."
                        if self.feedback_enabled
                        else "",
                    )
                if self.feedback_enabled:
                    feedback = scores[-1]
                    scores = scores[:-1]

            if self.analysis_only:
                break

            if scores == "s":
                break
            if scores == "b":
                continue
            if scores == "r":
                # run again, but don't build
                build = False
                continue

            # Record score
            for first_name, last_name, net_id in zip(first_names, last_names, net_ids):
                row_idx = grades_csv.find_idx_for_netid(student_grades_df, net_id)

                for i, col in enumerate(self.csv_col_names):
                    student_grades_df.at[row_idx, col] = scores[i]

                if self.feedback_col_name:
                    existing_feedback = student_grades_df.at[
                        row_idx, self.feedback_col_name
                    ].strip()
                    if existing_feedback and (existing_feedback[-1] != "."):
                        existing_feedback += ". "

                    # Append new feedback
                    student_grades_df.at[row_idx, self.feedback_col_name] = (
                        existing_feedback + feedback
                    )

                # Save feedback to a file
                if self.feedback_filename:
                    feedback_file_path = self.feedback_dir_path / (
                        first_name
                        + "_"
                        + last_name
                        + "_"
                        + net_id
                        + "_feedback-"
                        + self.feedback_filename
                        + ".txt"
                    )
                    with open(feedback_file_path, "a", encoding="utf-8") as f:
                        f.write(feedback + "\n")

                    # Create zip archive
                    if self.feedback_zip_path.is_file():
                        self.feedback_zip_path.unlink()
                    shutil.make_archive(
                        self.feedback_zip_path.with_suffix(""), "zip", self.feedback_dir_path
                    )

            student_grades_df.to_csv(
                str(self.grader.grades_csv_path),
                index=False,
                quoting=csv.QUOTE_ALL,
            )
            break

    def num_grades_needed(self, row):
        """Return the number of total grades needed across all group members for
        each grade column in this row."""
        empty_per_col = []
        for col in self.csv_col_names:
            empty_cnt = 0
            for grade in row[col]:
                if pandas.isnull(grade):
                    empty_cnt += 1
            empty_per_col.append(empty_cnt)
        return empty_per_col

    def _get_scores(self, names):
        """Prompts the user for a score for the grade column(s)."""
        fpad = " " * 8
        fpad2 = " " * 4
        pad = 10
        feedback = ""
        scores = []

        for i, grade_col in enumerate(self.csv_col_names):
            points = self.max_points[i] if self.max_points else None
            while True:
                print("")
                if self.help_msg:
                    print_color(TermColors.BOLD, self.help_msg[i])

                ################### Build input menu #######################
                input_txt = (
                    TermColors.BLUE
                    + "Enter a grade for "
                    + names
                    + ", "
                    + (TermColors.UNDERLINE + grade_col + TermColors.END + TermColors.BLUE)
                    + ":\n"
                )

                # Add current feedback
                if self.feedback_enabled:
                    input_txt += (
                        fpad
                        + "Pending feedback: "
                        + TermColors.END
                        + feedback
                        + TermColors.BLUE
                        + "\n"
                    )

                # Add score input
                input_txt += (
                    fpad2
                    + (("0-" + str(points)) if points else "#").ljust(pad)
                    + "Enter a score to finish and save\n"
                )

                # Enter feedback
                allowed_feedback = {}
                if self.feedback_enabled:
                    input_txt += (
                        fpad2
                        + "str".ljust(pad)
                        + "Enter a string with any new feedback, or select from previous feedback:\n"
                    )
                    for idx, f in enumerate(self.feedback_list):
                        input_txt += fpad2 + ("f" + str(idx)).ljust(pad + 2) + f + "\n"
                        allowed_feedback["f" + str(idx)] = f

                    input_txt += fpad2 + "'c'".ljust(pad) + "Clear entered feedback\n"
                    allowed_feedback["c"] = ""

                input_txt += fpad2 + "'s'".ljust(pad) + "Skip to next student\n"
                allowed_cmds = ["s"]

                if self.grader.allow_rebuild:
                    input_txt += fpad2 + "'b'".ljust(pad) + "Build and run again\n"
                    allowed_cmds.append("b")
                if self.grader.allow_rerun:
                    input_txt += fpad2 + "'r'".ljust(pad) + "Re-run"
                    if self.grader.allow_rebuild:
                        input_txt += " (w/o rebuild)"
                    input_txt += "\n"
                    allowed_cmds.append("r")

                # Remove trailing ", " and terminate
                input_txt += ">>> " + TermColors.END

                ################### Get and handle user input #######################
                txt = input(input_txt)

                # Check for commands
                if txt in allowed_cmds:
                    scores = txt
                    break

                # Check for integer input
                try:
                    score = float(txt)
                    if (points is None) or (0 <= score <= points):
                        scores.append(score)
                        break
                    print("Invalid input. Try again.")
                except ValueError:
                    pass

                # Check for feedback input
                if txt in allowed_feedback:
                    if txt == "c":
                        feedback = ""
                        continue
                    feedback_to_add = allowed_feedback[txt]

                else:
                    txt = txt.capitalize()
                    if txt not in self.feedback_list:
                        self.feedback_list.append(txt)
                        with open(self.feedback_list_path, "w", encoding="utf-8") as f:
                            json.dump(self.feedback_list, f)
                    feedback_to_add = txt

                # Assume input is feedback
                if feedback and feedback[-1] != ".":
                    feedback += ". "
                feedback += feedback_to_add

            # If non-integer returned, then user asked for something like re-run, so stop prompting for grades and exit this function
            if isinstance(scores, str):
                return (scores, "")

        return (scores, feedback)
