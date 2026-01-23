"""Module for generating student feedback files."""

import pathlib
import zipfile
from typing import Dict

import pandas

from .deductions import StudentDeductions
from .grading_item_config import LearningSuiteColumn


def generate_feedback_zip(
    yaml_path: pathlib.Path,
    class_list_csv_path: pathlib.Path,
    subitem_feedback_paths: Dict[str, pathlib.Path],
    output_zip_path: pathlib.Path = None,
) -> pathlib.Path:
    """Generate a zip file containing feedback files for each student.

    Args:
        yaml_path: Path to the YAML file that can be loaded by LearningSuiteColumn.
        class_list_csv_path: Path to CSV file with class list (Net ID, First Name, Last Name).
        subitem_feedback_paths: Mapping from subitem name to feedback YAML file path.
        output_zip_path: Path for the output zip file. If None, defaults to
            <yaml_dir>/feedback.zip.

    Returns:
        Path to the generated zip file.
    """
    yaml_path = pathlib.Path(yaml_path)
    ls_column = LearningSuiteColumn(yaml_path)

    # Get the lab name from the YAML file's parent directory
    lab_name = yaml_path.stem

    # Default output path
    if output_zip_path is None:
        output_zip_path = yaml_path.parent / "feedback.zip"

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

    # Load class list from provided CSV
    students_df = pandas.read_csv(class_list_csv_path)

    # Create the zip file
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for _, student_row in students_df.iterrows():
            first_name = str(student_row["First Name"]).strip()
            last_name = str(student_row["Last Name"]).strip()
            net_id = str(student_row["Net ID"]).strip()

            # Generate feedback content for this student
            feedback_content = _generate_student_feedback(
                student_row=student_row,
                ls_column=ls_column,
                subitem_deductions=subitem_deductions,
            )

            # Generate filename
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

            # Add to zip file
            zip_file.writestr(filename, feedback_content)

    return output_zip_path


def _generate_student_feedback(
    student_row: pandas.Series,
    ls_column: LearningSuiteColumn,
    subitem_deductions: Dict[str, StudentDeductions],
) -> str:
    """Generate the feedback text content for a single student.

    Args:
        student_row: A row from the student DataFrame.
        ls_column: The LearningSuiteColumn object.
        subitem_deductions: Mapping from subitem name to StudentDeductions.

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
    feedback_col_width = 45
    points_col_width = 15

    for item in ls_column.items:
        subitem_points_possible = item.points
        total_points_possible += subitem_points_possible

        lines.append(f"{item.name} ({subitem_points_possible} points)")
        lines.append("-" * 60)

        # Header row
        header = f"{'Feedback':<{feedback_col_width}} {'Points Deducted':>{points_col_width}}"
        lines.append(header)
        lines.append("-" * 60)

        subitem_points_deducted = 0

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
                    feedback_text = deduction.message
                    points = deduction.points

                    # Wrap long feedback text
                    wrapped_lines = _wrap_text(feedback_text, feedback_col_width)
                    for i, line_text in enumerate(wrapped_lines):
                        if i == 0:
                            row = f"{line_text:<{feedback_col_width}} {points:>{points_col_width}.1f}"
                        else:
                            row = f"{line_text:<{feedback_col_width}} {'':{points_col_width}}"
                        lines.append(row)

                    subitem_points_deducted += points

        if subitem_points_deducted == 0:
            lines.append(
                f"{'No deductions':<{feedback_col_width}} {'0.0':>{points_col_width}}"
            )

        lines.append("-" * 60)
        subitem_score = subitem_points_possible - subitem_points_deducted
        lines.append(
            f"{'Subitem Total:':<{feedback_col_width}} {subitem_score:>{points_col_width}.1f} / {subitem_points_possible:.1f}"
        )
        lines.append("")

        total_points_deducted += subitem_points_deducted

    # Total score section
    lines.append("=" * 60)
    total_score = total_points_possible - total_points_deducted
    lines.append(
        f"{'TOTAL SCORE:':<{feedback_col_width}} {total_score:>{points_col_width}.1f} / {total_points_possible:.1f}"
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
