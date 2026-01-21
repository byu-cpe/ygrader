"""Module for prompting users for scores during grading."""

from enum import Enum, auto

from .utils import TermColors, print_color


class ScoreResult(Enum):
    """Enum representing special score input results."""

    SKIP = auto()
    REBUILD = auto()
    RERUN = auto()
    CREATE_DEDUCTION = auto()


def get_score(
    names,
    csv_col_name,
    max_points,
    help_msg,
    allow_rebuild,
    allow_rerun,
    student_deductions=None,
    net_ids=None,
):
    """Prompts the user for a score for the grade column.

    Args:
        names: Student name(s) to display
        csv_col_name: Name of the CSV column being graded
        max_points: Maximum points for this item (or None if no limit)
        help_msg: Optional help message to display
        allow_rebuild: Whether rebuild option is available
        allow_rerun: Whether rerun option is available
        student_deductions: StudentDeductions object (for DEDUCTIONS mode)
        net_ids: Tuple of net_ids for the current student (for DEDUCTIONS mode)

    Returns:
        Either a numeric score (float) or a ScoreResult enum value
    """
    fpad2 = " " * 4
    pad = 10

    # Check if we're in deductions mode
    deductions_mode = student_deductions is not None and net_ids is not None

    while True:
        # Compute score if in deductions mode
        computed_score = None
        if deductions_mode:
            deductions_total = student_deductions.total_deductions(tuple(net_ids))
            computed_score = max(0, max_points - deductions_total)

        print("")
        print("-" * 60)
        if help_msg:
            print_color(TermColors.BOLD, help_msg)

        # Show current deductions for this student if in deductions mode (in white)
        if deductions_mode:
            current_deductions = student_deductions.get_student_deductions(
                tuple(net_ids)
            )
            print(
                fpad2
                + f"Current score: {TermColors.GREEN}{computed_score}{TermColors.END}"
            )
            print(fpad2 + "Current deductions:")
            if current_deductions:
                for d in current_deductions:
                    print(fpad2 + f"  -{d.points}: {d.message}")
            else:
                print(fpad2 + "  (None)")
            print("")

        ################### Build input menu #######################
        # Build menu items for two-column display (left_items, right_items)
        left_items = []
        right_items = []
        allowed_cmds = {}

        # Show computed score if in deductions mode
        if deductions_mode:
            left_items.append(("[Enter]", "Accept score"))
        else:
            # Add score input (only for manual mode)
            key = ("0-" + str(max_points)) if max_points else "#"
            left_items.append((key, "Enter score"))

        left_items.append(("[s]", "Skip student"))
        allowed_cmds["s"] = ScoreResult.SKIP

        if allow_rebuild:
            left_items.append(("[b]", "Build & run"))
            allowed_cmds["b"] = ScoreResult.REBUILD
        if allow_rerun:
            desc = "Re-run" if not allow_rebuild else "Re-run (no build)"
            left_items.append(("[r]", desc))
            allowed_cmds["r"] = ScoreResult.RERUN

        # Add deduction options to right column (only in deductions mode)
        if deductions_mode:
            right_items.append(("[c]", "Create deduction"))
            allowed_cmds["c"] = "create"

            right_items.append(("[d]", "Delete deduction"))
            allowed_cmds["d"] = "delete"

            right_items.append(("[0]", "Clear deductions"))

        # Format menu items in two columns
        col_width = 38  # Each column width (2 columns * 38 = 76 < 80)
        input_txt = (
            TermColors.BLUE
            + "Enter a grade for "
            + names
            + ", "
            + (TermColors.UNDERLINE + csv_col_name + TermColors.END + TermColors.BLUE)
            + ":"
            + TermColors.END
            + "\n"
        )

        # Combine left and right items row by row
        max_rows = max(len(left_items), len(right_items))
        for i in range(max_rows):
            # Left column
            if i < len(left_items):
                key1, desc1 = left_items[i]
                col1 = (
                    fpad2 + TermColors.BLUE + key1.ljust(pad) + TermColors.END + desc1
                )
                # Pad to column width (accounting for ANSI codes)
                col1_visible_len = len(fpad2) + len(key1.ljust(pad)) + len(desc1)
                col1_padded = col1 + " " * (col_width - col1_visible_len)
            else:
                col1_padded = " " * col_width

            # Right column
            if i < len(right_items):
                key2, desc2 = right_items[i]
                col2 = TermColors.BLUE + key2.ljust(pad) + TermColors.END + desc2
                input_txt += col1_padded + col2 + "\n"
            else:
                input_txt += col1_padded.rstrip() + "\n"

        # Show available deduction types to apply (keep single column for these)
        if deductions_mode:
            input_txt += fpad2 + "Apply deduction(s):\n"
            for (
                deduction_id,
                deduction_type,
            ) in student_deductions.deduction_types.items():
                input_txt += (
                    fpad2
                    + TermColors.BLUE
                    + f"  [{deduction_id}]".ljust(pad)
                    + TermColors.END
                    + f"-{deduction_type.points}: {deduction_type.message}\n"
                )

        input_txt += TermColors.BLUE + ">>> " + TermColors.END

        ################### Get and handle user input #######################
        txt = input(input_txt)

        # Check for Enter key to accept computed score
        if txt == "" and deductions_mode:
            print(f"Saving score: {computed_score}")
            return computed_score

        # Check for commands
        if txt in allowed_cmds:
            result = allowed_cmds[txt]

            # Handle special cases that need to loop back
            if result == "create":
                deduction_id = student_deductions.create_deduction_type_interactive()
                if deduction_id >= 0:
                    # Auto-apply the new deduction to this student
                    student_deductions.apply_deduction_to_student(
                        tuple(net_ids), deduction_id
                    )
                continue
            elif result == "delete":
                student_deductions.delete_deduction_type_interactive()
                continue
            else:
                return result

        # Check for deduction ID input (only in deductions mode)
        # 0 is reserved for clearing all deductions (must be standalone, not in a list)
        # Supports comma-separated list of deduction IDs (e.g., "1,2,3")
        if deductions_mode:
            # Check for clear command (must be exactly "0", not in a list)
            if txt == "0":
                student_deductions.clear_student_deductions(tuple(net_ids))
                print("Cleared all deductions for this student.")
                continue

            # Split by comma and try to parse each as a deduction ID
            parts = [p.strip() for p in txt.split(",")]
            valid_ids = []
            all_valid = True
            for part in parts:
                try:
                    deduction_id = int(part)
                    # Don't allow 0 or other special commands in the list
                    if deduction_id <= 0:
                        all_valid = False
                        break
                    elif deduction_id in student_deductions.deduction_types:
                        valid_ids.append(deduction_id)
                    else:
                        all_valid = False
                        break
                except ValueError:
                    all_valid = False
                    break

            if all_valid and valid_ids:
                # Apply the deductions
                for deduction_id in valid_ids:
                    student_deductions.apply_deduction_to_student(
                        tuple(net_ids), deduction_id
                    )
                    deduction_type = student_deductions.deduction_types[deduction_id]
                    print(
                        f"Applied deduction: {deduction_type.message} (-{deduction_type.points})"
                    )
                continue

        # Check for numeric input (only allowed in manual mode)
        if not deductions_mode:
            try:
                score = float(txt)
                if (max_points is None) or (0 <= score <= max_points):
                    return score
                print_color(TermColors.YELLOW, "Invalid input. Try again.")
            except ValueError:
                print_color(TermColors.YELLOW, "Invalid input. Try again.")
        else:
            print_color(TermColors.YELLOW, "Invalid input. Try again.")
