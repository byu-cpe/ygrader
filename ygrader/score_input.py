"""Module for prompting users for scores during grading."""

from enum import Enum, auto

from .utils import TermColors, print_color


class ScoreResult(Enum):
    """Enum representing special score input results."""

    SKIP = auto()
    REBUILD = auto()
    RERUN = auto()
    CREATE_DEDUCTION = auto()
    UNDO_LAST = auto()
    EXIT = auto()


def get_score(
    names,
    max_points,
    *,
    allow_rebuild=True,
    allow_rerun=True,
    student_deductions,
    net_ids,
    last_graded_net_ids=None,
    names_by_netid=None,
):
    """Prompts the user for a score for the grade column.

    Args:
        names: Student name(s) to display
        max_points: Maximum points for this item
        allow_rebuild: Whether rebuild option is available
        allow_rerun: Whether rerun option is available
        student_deductions: StudentDeductions object
        net_ids: Tuple of net_ids for the current student
        last_graded_net_ids: Tuple of net_ids for the last graded student (for undo)
        names_by_netid: Dict mapping net_id -> (first_name, last_name) for search

    Returns:
        Either a numeric score (float) or a ScoreResult enum value
    """
    fpad2 = " " * 4
    pad = 10

    while True:
        # Compute current score
        deductions_total = student_deductions.total_deductions(tuple(net_ids))
        computed_score = max(0, max_points - deductions_total)

        print("")
        print("-" * 60)

        # Show current deductions for this student
        current_deductions = student_deductions.get_student_deductions(tuple(net_ids))
        print(
            fpad2 + f"Current score: {TermColors.GREEN}{computed_score}{TermColors.END}"
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

        left_items.append(("[s]", "Skip student"))
        allowed_cmds["s"] = ScoreResult.SKIP

        if allow_rebuild:
            left_items.append(("[b]", "Build & run"))
            allowed_cmds["b"] = ScoreResult.REBUILD
        if allow_rerun:
            desc = "Re-run" if not allow_rebuild else "Re-run (no build)"
            left_items.append(("[r]", desc))
            allowed_cmds["r"] = ScoreResult.RERUN

        # Add deduction options to right column
        right_items.append(("[n]", "New deduction"))
        allowed_cmds["n"] = "create"

        right_items.append(("[d]", "Delete deduction"))
        allowed_cmds["d"] = "delete"

        right_items.append(("[0]", "Clear deductions"))

        right_items.append(("[v]", "Change deduction value"))
        allowed_cmds["v"] = "change_value"

        # Accept score at the bottom of right column
        right_items.append(("[Enter]", "Accept score"))

        # Add manage grades and undo to left column
        left_items.append(("[g]", "Manage grades"))
        allowed_cmds["g"] = "manage"

        # Add undo option if there's a last graded student
        if last_graded_net_ids is not None:
            left_items.append(("[u]", f"Undo last ({last_graded_net_ids[0]})"))
            allowed_cmds["u"] = ScoreResult.UNDO_LAST

        # Add exit option at bottom of left column
        left_items.append(("[e]", "Exit grader"))
        allowed_cmds["e"] = ScoreResult.EXIT

        # Format menu items in two columns
        col_width = 38  # Each column width (2 columns * 38 = 76 < 80)
        input_txt = (
            TermColors.BLUE + "Enter a grade for " + names + ":" + TermColors.END + "\n"
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

        # Show available deduction types to apply
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
        if txt == "":
            print(f"Saving score: {computed_score}")
            return computed_score

        # Check for commands
        if txt in allowed_cmds:
            result = allowed_cmds[txt]

            # Handle special cases that need to loop back
            if result == "create":
                deduction_id = student_deductions.create_deduction_type_interactive(
                    max_points=max_points
                )
                if deduction_id >= 0:
                    # Auto-apply the new deduction to this student
                    student_deductions.apply_deduction_to_student(
                        tuple(net_ids), deduction_id
                    )
                continue
            if result == "delete":
                student_deductions.delete_deduction_type_interactive()
                continue
            if result == "change_value":
                student_deductions.change_deduction_value_interactive(
                    max_points=max_points
                )
                continue
            if result == "manage":
                _manage_grades_interactive(student_deductions, names_by_netid)
                continue
            return result

        # Check for clear command (must be exactly "0", not in a list)
        if txt == "0":
            student_deductions.clear_student_deductions(tuple(net_ids))
            print("Cleared all deductions for this student.")
            continue

        # Check for deduction ID input
        # Supports comma-separated list of deduction IDs (e.g., "1,2,3")
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
                if deduction_id in student_deductions.deduction_types:
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

        print_color(TermColors.YELLOW, "Invalid input. Try again.")


def _manage_grades_interactive(student_deductions, names_by_netid=None):
    """Interactive menu to manage (view/delete) grades for any student.

    Args:
        student_deductions: StudentDeductions object to manage
        names_by_netid: Dict mapping net_id -> (first_name, last_name) for search
    """
    while True:
        graded_students = student_deductions.get_graded_students()

        print("\n" + "=" * 60)
        print_color(TermColors.BLUE, "Manage Grades")
        print("=" * 60)

        if not graded_students:
            print("No students have been graded yet.")
            input("Press Enter to continue...")
            return

        print(f"{len(graded_students)} student(s) graded.")
        print("\nOptions:")
        print("  [search]  Enter search string to find student by name or net_id")
        print("  [*]       List all graded students")
        print("  [Enter]   Return to grading")

        txt = input("\nSearch: ").strip()

        if txt == "":
            return

        # Check for wildcard to list all
        list_all = txt == "*"

        # Search for matching students (case-insensitive)
        search_lower = txt.lower()
        matches = []

        for net_ids in graded_students:
            match_found = list_all  # If listing all, match everything
            display_parts = []

            for net_id in net_ids:
                # Check if search matches net_id (skip if listing all)
                if not list_all and search_lower in net_id.lower():
                    match_found = True

                # Check if search matches first/last name
                if names_by_netid and net_id in names_by_netid:
                    first_name, last_name = names_by_netid[net_id]
                    if not list_all and (
                        search_lower in first_name.lower()
                        or search_lower in last_name.lower()
                    ):
                        match_found = True
                    display_parts.append(f"{first_name} {last_name} ({net_id})")
                else:
                    display_parts.append(net_id)

            if match_found:
                matches.append((net_ids, ", ".join(display_parts)))

        if not matches:
            print_color(TermColors.YELLOW, f"No graded students match '{txt}'")
            continue

        # Sort matches by display name
        matches.sort(key=lambda x: x[1].lower())

        # Display matches and let user pick one
        print(f"\nFound {len(matches)} match(es):")
        for i, (net_ids, display) in enumerate(matches, 1):
            deductions = student_deductions.get_student_deductions(net_ids)
            deduction_count = len(deductions)
            total_deducted = student_deductions.total_deductions(net_ids)
            print(
                f"  [{i}] {display} "
                f"({deduction_count} deduction(s), -{total_deducted} pts)"
            )

        print("\n  [#]      Enter number to delete that student's grade")
        print("  [Enter]  Cancel")

        choice = input("\n>>> ").strip()

        if choice == "":
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                student_key, display = matches[idx]
                # Confirm deletion
                confirm = (
                    input(f"Delete grade for {display}? This cannot be undone. [y/N]: ")
                    .strip()
                    .lower()
                )

                if confirm == "y":
                    student_deductions.clear_student_deductions(student_key)
                    print_color(TermColors.GREEN, f"Deleted grade for {display}")
                else:
                    print("Cancelled.")
            else:
                print_color(TermColors.YELLOW, "Invalid selection.")
        except ValueError:
            print_color(TermColors.YELLOW, "Invalid input.")
