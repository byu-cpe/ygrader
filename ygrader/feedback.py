"""Module for generating student feedback files and grades CSV."""

import pathlib
import zipfile
from typing import Callable, Dict, Optional, Tuple

import pandas

from .deductions import StudentDeductions
from .grading_item_config import LearningSuiteColumn
from .utils import warning


# Type alias for late penalty callback: (late_days, max_score, actual_score) -> new_score
LatePenaltyCallback = Callable[[int, float, float], float]


def _get_student_key_and_max_late_days(
    net_id: str,
    item_deductions: Dict[str, StudentDeductions],
) -> tuple:
    """Find the student key and maximum late days across all items.

    Args:
        net_id: The student's net ID.
        item_deductions: Mapping from item name to StudentDeductions.

    Returns:
        Tuple of (student_key or None, max_late_days).
    """
    max_late_days = 0
    found_student_key = None

    for deductions_obj in item_deductions.values():
        if not deductions_obj:
            continue

        # Find the student key
        student_key = None
        if (net_id,) in deductions_obj.deductions_by_students:
            student_key = (net_id,)
        elif (net_id,) in deductions_obj.days_late_by_students:
            student_key = (net_id,)
        else:
            # Check for multi-student keys containing this net_id
            for key in set(deductions_obj.deductions_by_students.keys()) | set(
                deductions_obj.days_late_by_students.keys()
            ):
                if net_id in key:
                    student_key = key
                    break

        if student_key:
            found_student_key = student_key
            days_late = deductions_obj.days_late_by_students.get(student_key, 0)
            max_late_days = max(max_late_days, days_late)

    return found_student_key, max_late_days


def _calculate_student_score(
    net_id: str,
    ls_column: LearningSuiteColumn,
    item_deductions: Dict[str, StudentDeductions],
    late_penalty_callback: Optional[LatePenaltyCallback] = None,
    warn_on_missing_callback: bool = True,
) -> Tuple[float, float, int]:
    """Calculate a student's final score.

    Args:
        net_id: The student's net ID.
        ls_column: The LearningSuiteColumn configuration.
        item_deductions: Mapping from item name to StudentDeductions.
        late_penalty_callback: Optional callback for late penalty.
        warn_on_missing_callback: Whether to warn if late days found but no callback.

    Returns:
        Tuple of (final_score, total_possible, max_late_days).
    """
    total_possible = sum(item.points for item in ls_column.items)
    total_deductions = 0.0

    for item in ls_column.items:
        deductions_obj = item_deductions.get(item.name)
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
                deductions = deductions_obj.deductions_by_students[student_key]
                for deduction in deductions:
                    total_deductions += deduction.points

    # Calculate score before late penalty
    score = max(0, total_possible - total_deductions)

    # Get max late days
    _, max_late_days = _get_student_key_and_max_late_days(net_id, item_deductions)

    # Apply late penalty if applicable
    if max_late_days > 0:
        if late_penalty_callback:
            score = max(0, late_penalty_callback(max_late_days, total_possible, score))
        elif warn_on_missing_callback:
            warning(
                f"Student {net_id} has {max_late_days} late day(s) but no late penalty callback provided"
            )

    return score, total_possible, max_late_days


def assemble_grades(
    yaml_path: pathlib.Path,
    class_list_csv_path: pathlib.Path,
    subitem_feedback_paths: Dict[str, pathlib.Path],
    output_zip_path: Optional[pathlib.Path] = None,
    output_csv_path: Optional[pathlib.Path] = None,
    late_penalty_callback: Optional[LatePenaltyCallback] = None,
) -> Tuple[Optional[pathlib.Path], Optional[pathlib.Path]]:
    """Generate feedback zip and/or grades CSV from deductions.

    Args:
        yaml_path: Path to the YAML file that can be loaded by LearningSuiteColumn.
        class_list_csv_path: Path to CSV file with class list (Net ID, First Name, Last Name).
        subitem_feedback_paths: Mapping from subitem name to feedback YAML file path.
        output_zip_path: Path for the output zip file. If None, no zip is generated.
        output_csv_path: Path for the output CSV file. If None, no CSV is generated.
        late_penalty_callback: Optional callback function that takes
            (late_days, max_score, actual_score) and returns the adjusted score.

    Returns:
        Tuple of (feedback_zip_path or None, grades_csv_path or None).
    """
    yaml_path = pathlib.Path(yaml_path)
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

    # Prepare for zip output
    zip_file = None
    if output_zip_path:
        zip_file = zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED)

    try:
        for _, student_row in students_df.iterrows():
            first_name = str(student_row["First Name"]).strip()
            last_name = str(student_row["Last Name"]).strip()
            net_id = str(student_row["Net ID"]).strip()

            # Calculate final score (only warn once, when generating CSV)
            final_score, _, _ = _calculate_student_score(
                net_id=net_id,
                ls_column=ls_column,
                item_deductions=subitem_deductions,
                late_penalty_callback=late_penalty_callback,
                warn_on_missing_callback=(output_csv_path is not None),
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

    finally:
        if zip_file:
            zip_file.close()

    # Write CSV
    if output_csv_path and grades_data:
        grades_df = pandas.DataFrame(grades_data)
        grades_df.to_csv(output_csv_path, index=False)

    return (output_zip_path, output_csv_path)


def _generate_student_feedback(
    student_row: pandas.Series,
    ls_column: LearningSuiteColumn,
    subitem_deductions: Dict[str, StudentDeductions],
    late_penalty_callback: Optional[LatePenaltyCallback] = None,
) -> str:
    """Generate the feedback text content for a single student.

    Args:
        student_row: A row from the student DataFrame.
        ls_column: The LearningSuiteColumn object.
        subitem_deductions: Mapping from subitem name to StudentDeductions.
        late_penalty_callback: Optional callback for calculating late penalty.

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
        item_deductions = []

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
                deductions = student_deductions_obj.deductions_by_students[student_key]
                for deduction in deductions:
                    item_deductions.append((deduction.message, deduction.points))
                    subitem_points_deducted += deduction.points

        # Calculate item score
        subitem_score = max(0, subitem_points_possible - subitem_points_deducted)
        score_str = f"{subitem_score:.1f} / {subitem_points_possible:.1f}"

        # Item line with score
        item_name_with_colon = f"{item.name}:"
        lines.append(
            f"{item_name_with_colon:<{item_col_width}} {score_str:>{score_col_width}}"
        )

        # Deduction lines (indented)
        for msg, pts in item_deductions:
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

    # Get max late days for this student
    _, max_late_days = _get_student_key_and_max_late_days(net_id, subitem_deductions)

    # Late penalty section
    lines.append("")
    lines.append("=" * 60)
    if max_late_days > 0 and late_penalty_callback:
        final_score = late_penalty_callback(
            max_late_days, total_points_possible, score_before_late
        )
        # Ensure final score is not negative
        final_score = max(0, final_score)
        late_penalty_points = score_before_late - final_score
        late_label = (
            f"Late Penalty ({max_late_days} day{'s' if max_late_days != 1 else ''}):"
        )
        lines.append(
            f"{late_label:<{item_col_width}} {-late_penalty_points:>{score_col_width}.1f}"
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
