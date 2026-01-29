"""Module for generating student feedback files and grades CSV."""

import datetime
import pathlib
import zipfile
from typing import Callable, Dict, Optional, Tuple

import pandas
import yaml

from .deductions import StudentDeductions
from .grading_item_config import LearningSuiteColumn
from .utils import warning, print_color, TermColors


# Type alias for late penalty callback:
# (due_datetime, submitted_datetime, max_score, actual_score) -> new_score
# If submitted_datetime is None, the student submitted on time or no submit time was recorded.
LatePenaltyCallback = Callable[
    [datetime.datetime, Optional[datetime.datetime], float, float], float
]


def _load_due_date_exceptions(
    exceptions_path: pathlib.Path,
) -> Dict[str, datetime.datetime]:
    """Load due date exceptions from YAML file.

    Args:
        exceptions_path: Path to the deadline_exceptions.yaml file.
            Expected format is: net_id: "YYYY-MM-DD HH:MM:SS"

    Returns:
        Mapping from net_id to exception datetime.
    """
    if not exceptions_path.exists():
        return {}

    with open(exceptions_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return {}

    exceptions = {}
    for net_id, exception_date in data.items():
        if net_id and exception_date:
            exceptions[net_id] = datetime.datetime.strptime(
                exception_date, "%Y-%m-%d %H:%M:%S"
            )
    return exceptions


def _get_student_key_and_submit_info(
    net_id: str,
    item_deductions: Dict[str, StudentDeductions],
    due_date: Optional[datetime.datetime] = None,
    due_date_exceptions: Optional[Dict[str, datetime.datetime]] = None,
) -> Tuple[Optional[tuple], Optional[datetime.datetime], Optional[datetime.datetime]]:
    """Find the student key and submission timing info across all items.

    Args:
        net_id: The student's net ID.
        item_deductions: Mapping from item name to StudentDeductions.
        due_date: The default due date for the assignment.
        due_date_exceptions: Mapping from net_id to exception due date.

    Returns:
        Tuple of (student_key or None, effective_due_date or None, latest_submit_time or None).
        latest_submit_time is None if on time or no submit time recorded.
    """
    found_student_key = None
    latest_submit_time: Optional[datetime.datetime] = None
    effective_due_date: Optional[datetime.datetime] = due_date

    if due_date_exceptions is None:
        due_date_exceptions = {}

    for deductions_obj in item_deductions.values():
        if not deductions_obj:
            continue

        # Find the student key
        student_key = None
        if (net_id,) in deductions_obj.deductions_by_students:
            student_key = (net_id,)
        elif (net_id,) in deductions_obj.submit_time_by_students:
            student_key = (net_id,)
        else:
            # Check for multi-student keys containing this net_id
            for key in set(deductions_obj.deductions_by_students.keys()) | set(
                deductions_obj.submit_time_by_students.keys()
            ):
                if net_id in key:
                    student_key = key
                    break

        if student_key:
            found_student_key = student_key

            # Calculate effective due date (using most generous exception for group)
            if due_date is not None:
                effective_due_date = due_date
                for member_net_id in student_key:
                    if member_net_id in due_date_exceptions:
                        effective_due_date = max(
                            effective_due_date, due_date_exceptions[member_net_id]
                        )

            # Get submit time
            submit_time_str = deductions_obj.submit_time_by_students.get(student_key)
            if submit_time_str:
                try:
                    submit_time = datetime.datetime.fromisoformat(submit_time_str)
                    # Track latest submit time across all items
                    if latest_submit_time is None or submit_time > latest_submit_time:
                        latest_submit_time = submit_time
                except ValueError:
                    pass

    # Return None for submit_time if on time
    if (
        latest_submit_time is not None
        and effective_due_date is not None
        and latest_submit_time <= effective_due_date
    ):
        latest_submit_time = None

    return found_student_key, effective_due_date, latest_submit_time


def _calculate_student_score(
    net_id: str,
    ls_column: LearningSuiteColumn,
    item_deductions: Dict[str, StudentDeductions],
    *,
    late_penalty_callback: Optional[LatePenaltyCallback] = None,
    warn_on_missing_callback: bool = True,
    due_date: Optional[datetime.datetime] = None,
    due_date_exceptions: Optional[Dict[str, datetime.datetime]] = None,
) -> Tuple[float, float, Optional[datetime.datetime]]:
    """Calculate a student's final score.

    Args:
        net_id: The student's net ID.
        ls_column: The LearningSuiteColumn configuration.
        item_deductions: Mapping from item name to StudentDeductions.
        late_penalty_callback: Optional callback for late penalty.
        warn_on_missing_callback: Whether to warn if late but no callback.
        due_date: The default due date for the assignment.
        due_date_exceptions: Mapping from net_id to exception due date.

    Returns:
        Tuple of (final_score, total_possible, submitted_datetime or None if on time).
    """
    total_possible = sum(item.points for item in ls_column.items)
    total_score = 0.0

    for item in ls_column.items:
        deductions_obj = item_deductions.get(item.name)
        student_graded = False
        item_deduction_total = 0.0

        if deductions_obj:
            # Find the student's deductions
            student_key = None
            if (net_id,) in deductions_obj.deductions_by_students:
                student_key = (net_id,)
            else:
                for key in deductions_obj.deductions_by_students.keys():
                    if net_id in key:
                        student_key = key
                        break

            if student_key:
                student_graded = True
                deductions = deductions_obj.deductions_by_students[student_key]
                for deduction in deductions:
                    item_deduction_total += deduction.points

        # Only award points if the student was graded for this item
        if student_graded:
            total_score += max(0, item.points - item_deduction_total)
        # else: student gets 0 for this item (not graded)

    # Score is already calculated
    score = total_score

    # Get submit info
    _, effective_due_date, submitted_datetime = _get_student_key_and_submit_info(
        net_id, item_deductions, due_date, due_date_exceptions
    )

    # Apply late penalty if applicable (submitted_datetime is None if on time)
    if submitted_datetime is not None:
        if late_penalty_callback and effective_due_date is not None:
            score = max(
                0,
                late_penalty_callback(
                    effective_due_date, submitted_datetime, total_possible, score
                ),
            )
        elif warn_on_missing_callback:
            warning(
                f"Student {net_id} submitted late but no late penalty callback provided"
            )

    return score, total_possible, submitted_datetime


def assemble_grades(
    yaml_path: pathlib.Path,
    class_list_csv_path: pathlib.Path,
    subitem_feedback_paths: Dict[str, pathlib.Path],
    *,
    output_zip_path: Optional[pathlib.Path] = None,
    output_csv_path: Optional[pathlib.Path] = None,
    late_penalty_callback: Optional[LatePenaltyCallback] = None,
    due_date: Optional[datetime.datetime] = None,
    due_date_exceptions_path: Optional[pathlib.Path] = None,
) -> Tuple[Optional[pathlib.Path], Optional[pathlib.Path]]:
    """Generate feedback zip and/or grades CSV from deductions.

    Args:
        yaml_path: Path to the YAML file that can be loaded by LearningSuiteColumn.
        class_list_csv_path: Path to CSV file with class list (Net ID, First Name, Last Name).
        subitem_feedback_paths: Mapping from subitem name to feedback YAML file path.
        output_zip_path: Path for the output zip file. If None, no zip is generated.
        output_csv_path: Path for the output CSV file. If None, no CSV is generated.
        late_penalty_callback: Optional callback function that takes
            (due_datetime, submitted_datetime, max_score, actual_score) and returns the adjusted score.
            submitted_datetime will be None if on time.
        due_date: The default due date for the assignment. Required for late penalty.
        due_date_exceptions_path: Path to YAML file with due date exceptions (net_id: "YYYY-MM-DD HH:MM:SS").

    Returns:
        Tuple of (feedback_zip_path or None, grades_csv_path or None).
    """
    yaml_path = pathlib.Path(yaml_path)

    # Load due date exceptions if path provided
    due_date_exceptions: Dict[str, datetime.datetime] = {}
    if due_date_exceptions_path:
        due_date_exceptions = _load_due_date_exceptions(due_date_exceptions_path)
    ls_column = LearningSuiteColumn(yaml_path)

    # Get the lab name from the YAML file's parent directory
    lab_name = yaml_path.parent.name

    # Load all student deductions for each subitem
    subitem_deductions: Dict[str, StudentDeductions] = {}
    for subitem in ls_column.items:
        if subitem.name in subitem_feedback_paths:
            feedback_path = subitem_feedback_paths[subitem.name]
            if feedback_path.exists():
                subitem_deductions[subitem.name] = StudentDeductions(feedback_path)
            else:
                subitem_deductions[subitem.name] = StudentDeductions()
        else:
            subitem_deductions[subitem.name] = StudentDeductions()

    # Load class list
    students_df = pandas.read_csv(class_list_csv_path)

    # Prepare for CSV output
    grades_data = []

    def process_students(zip_file: Optional[zipfile.ZipFile]) -> None:
        """Process all students, adding to grades_data and optionally writing to zip."""
        for _, student_row in students_df.iterrows():
            first_name = str(student_row["First Name"]).strip()
            last_name = str(student_row["Last Name"]).strip()
            net_id = str(student_row["Net ID"]).strip()

            # Check for partial grades (graded for some items but not others)
            items_graded = []
            items_not_graded = []
            for item in ls_column.items:
                deductions_obj = subitem_deductions.get(item.name)
                if deductions_obj and deductions_obj.is_student_graded((net_id,)):
                    items_graded.append(item.name)
                else:
                    # Also check for multi-student keys containing this net_id
                    found = False
                    if deductions_obj:
                        for key in deductions_obj.deductions_by_students.keys():
                            if net_id in key:
                                items_graded.append(item.name)
                                found = True
                                break
                    if not found:
                        items_not_graded.append(item.name)

            if items_graded and items_not_graded:
                print_color(
                    TermColors.RED,
                    f"Partial grade: {net_id} graded for [{', '.join(items_graded)}] "
                    f"but NOT [{', '.join(items_not_graded)}]",
                )

            # Check if student has no grades at all
            student_graded = len(items_graded) > 0
            if not student_graded:
                print_color(
                    TermColors.YELLOW,
                    f"No grades: {net_id} has no grades, receiving 0",
                )

            # Get submit info for this student
            _, effective_due_date, submitted_datetime = (
                _get_student_key_and_submit_info(
                    net_id, subitem_deductions, due_date, due_date_exceptions
                )
            )

            # Calculate score before late penalty
            score_before_late, total_possible, _ = _calculate_student_score(
                net_id=net_id,
                ls_column=ls_column,
                item_deductions=subitem_deductions,
                late_penalty_callback=None,  # Don't apply late penalty yet
                warn_on_missing_callback=False,
                due_date=due_date,
                due_date_exceptions=due_date_exceptions,
            )

            # Apply late penalty if applicable (submitted_datetime is None if on time)
            final_score = score_before_late
            if (
                submitted_datetime is not None
                and late_penalty_callback
                and effective_due_date is not None
            ):
                final_score = max(
                    0,
                    late_penalty_callback(
                        effective_due_date,
                        submitted_datetime,
                        total_possible,
                        score_before_late,
                    ),
                )
                print_color(
                    TermColors.YELLOW,
                    f"Late: {net_id} (submitted {submitted_datetime}): "
                    f"{score_before_late:.1f} -> {final_score:.1f}",
                )

            # Add to grades data
            if output_csv_path:
                grades_data.append(
                    {"Net ID": net_id, ls_column.csv_col_name: final_score}
                )

            # Generate feedback file
            if zip_file:
                feedback_content = _generate_student_feedback(
                    student_row=student_row,
                    ls_column=ls_column,
                    subitem_deductions=subitem_deductions,
                    late_penalty_callback=late_penalty_callback,
                    due_date=due_date,
                    due_date_exceptions=due_date_exceptions,
                    student_graded=student_graded,
                )

                filename = (
                    first_name
                    + "_"
                    + last_name
                    + "_"
                    + net_id
                    + "_feedback-"
                    + lab_name
                    + ".txt"
                )
                zip_file.writestr(filename, feedback_content)

    # Process students with or without zip file
    if output_zip_path:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            process_students(zf)
    else:
        process_students(None)

    # Write CSV (sorted by Net ID for easier git diffs)
    if output_csv_path and grades_data:
        grades_df = pandas.DataFrame(grades_data)
        grades_df = grades_df.sort_values("Net ID")
        grades_df.to_csv(output_csv_path, index=False)

    return (output_zip_path, output_csv_path)


def _generate_student_feedback(
    student_row: pandas.Series,
    ls_column: LearningSuiteColumn,
    subitem_deductions: Dict[str, StudentDeductions],
    *,
    late_penalty_callback: Optional[LatePenaltyCallback] = None,
    due_date: Optional[datetime.datetime] = None,
    due_date_exceptions: Optional[Dict[str, datetime.datetime]] = None,
    student_graded: bool = True,
) -> str:
    """Generate the feedback text content for a single student.

    Args:
        student_row: A row from the student DataFrame.
        ls_column: The LearningSuiteColumn object.
        subitem_deductions: Mapping from subitem name to StudentDeductions.
        late_penalty_callback: Optional callback for calculating late penalty.
        due_date: The default due date for the assignment.
        due_date_exceptions: Mapping from net_id to exception due date.
        student_graded: Whether the student was graded at all (False if no submission).

    Returns:
        The formatted feedback text.
    """
    net_id = str(student_row["Net ID"]).strip()
    first_name = str(student_row["First Name"]).strip()
    last_name = str(student_row["Last Name"]).strip()

    lines = []
    lines.append(f"Feedback for {first_name} {last_name} ({net_id})")
    lines.append("=" * 60)
    lines.append("")

    total_points_possible = 0
    total_points_deducted = 0

    # Column widths for formatting
    # Total width is 60 characters to match separator lines
    # Item name column + score column (e.g., "10.0 / 10.0")
    item_col_width = 42
    score_col_width = 17
    # For deduction lines: "  - " prefix (4 chars) + message + points
    deduction_prefix = "  - "
    deduction_msg_width = 38
    deduction_pts_width = 17

    for item in ls_column.items:
        subitem_points_possible = item.points
        total_points_possible += subitem_points_possible

        subitem_points_deducted = 0
        item_deduction_list = []
        student_graded = False

        # Get deductions for this student in this item
        student_deductions_obj = subitem_deductions.get(item.name)
        if student_deductions_obj:
            # Find the student's deductions (try single net_id first, then tuple)
            student_key = None
            if (net_id,) in student_deductions_obj.deductions_by_students:
                student_key = (net_id,)
            else:
                # Check for multi-student keys containing this net_id
                for key in student_deductions_obj.deductions_by_students.keys():
                    if net_id in key:
                        student_key = key
                        break

            if student_key:
                student_graded = True
                deductions = student_deductions_obj.deductions_by_students[student_key]
                for deduction in deductions:
                    item_deduction_list.append((deduction.message, deduction.points))
                    subitem_points_deducted += deduction.points

        # Calculate item score (0 if not graded)
        if student_graded:
            subitem_score = max(0, subitem_points_possible - subitem_points_deducted)
        else:
            subitem_score = 0
            item_deduction_list.append(("Not graded", subitem_points_possible))
            subitem_points_deducted = subitem_points_possible
        score_str = f"{subitem_score:.1f} / {subitem_points_possible:.1f}"

        # Item line with score
        item_name_with_colon = f"{item.name}:"
        lines.append(
            f"{item_name_with_colon:<{item_col_width}} {score_str:>{score_col_width}}"
        )

        # Deduction lines (indented)
        for msg, pts in item_deduction_list:
            # Wrap long messages
            wrapped = _wrap_text(msg, deduction_msg_width)
            for i, line_text in enumerate(wrapped):
                if i == 0:
                    lines.append(
                        f"{deduction_prefix}{line_text:<{deduction_msg_width}} {-pts:>{deduction_pts_width}.1f}"
                    )
                else:
                    # Continuation lines - no points
                    lines.append(f"{deduction_prefix}{line_text}")

        total_points_deducted += subitem_points_deducted

    # Calculate score before late penalty (clamped to 0)
    score_before_late = max(0, total_points_possible - total_points_deducted)

    # Get submit info for this student
    _, effective_due_date, submitted_datetime = _get_student_key_and_submit_info(
        net_id, subitem_deductions, due_date, due_date_exceptions
    )

    # Late penalty section
    lines.append("")
    lines.append("=" * 60)
    if (
        submitted_datetime is not None
        and late_penalty_callback
        and effective_due_date is not None
    ):
        final_score = late_penalty_callback(
            effective_due_date,
            submitted_datetime,
            total_points_possible,
            score_before_late,
        )
        # Ensure final score is not negative
        final_score = max(0, final_score)
        late_penalty_points = score_before_late - final_score
        late_label = (
            f"Late Penalty (submitted {submitted_datetime.strftime('%Y-%m-%d %H:%M')}):"
        )
        lines.append(
            f"{late_label:<{item_col_width}} {-late_penalty_points:>{score_col_width}.1f}"
        )
    elif not student_graded:
        # Student was never graded (no submission)
        final_score = score_before_late
        lines.append(
            f"{'Late Penalty:':<{item_col_width}} {'No Submission':>{score_col_width}}"
        )
    else:
        final_score = score_before_late
        lines.append(
            f"{'Late Penalty:':<{item_col_width}} {'On Time':>{score_col_width}}"
        )

    # Total score section
    total_score_str = f"{final_score:.1f} / {total_points_possible:.1f}"
    lines.append(
        f"{'TOTAL SCORE:':<{item_col_width}} {total_score_str:>{score_col_width}}"
    )
    lines.append("=" * 60)

    return "\n".join(lines)


def _wrap_text(text: str, width: int) -> list:
    """Wrap text to fit within a given width.

    Args:
        text: The text to wrap.
        width: Maximum width for each line.

    Returns:
        List of wrapped lines.
    """
    if len(text) <= width:
        return [text]

    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines if lines else [""]
