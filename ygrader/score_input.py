"""Module for prompting users for scores during grading."""

import sys
from enum import Enum

from .utils import TermColors, print_color


class MenuCommand(Enum):
    """Enum representing menu commands, with character as value.

    Used both for defining menu keys and as return values from get_score().
    """

    SKIP = "s"
    BUILD = "b"
    RERUN = "r"
    NEW_DEDUCTION = "n"
    DELETE_DEDUCTION = "d"
    CLEAR_DEDUCTIONS = "0"
    CHANGE_VALUE = "v"
    MANAGE_GRADES = "g"
    UNDO = "u"
    EXIT = "e"

    @property
    def key_display(self):
        """Return the key display string like '[s]'."""
        return f"[{self.value}]"


def _print_menu_item(cmd, description, indent="    ", pad=10):
    """Print a single menu item with consistent formatting."""
    print(
        indent
        + TermColors.BLUE
        + cmd.key_display.ljust(pad)
        + TermColors.END
        + description
    )


def display_completion_menu(items, names_by_netid=None):
    """Show a menu when all students have been graded.

    Allows the user to manage grades, edit deduction types, etc.

    Args:
        items: List of GradeItem objects (to access their student_deductions)
        names_by_netid: Dict mapping net_id -> (first_name, last_name) for search

    Returns:
        True if a grade was deleted (caller should re-run grading loop),
        False otherwise (user exited normally)
    """
    if not items:
        print_color(TermColors.YELLOW, "No grade items configured.")
        return True

    fpad2 = " " * 4

    while True:
        # Count total graded students across all items
        all_graded_students = set()
        for item in items:
            for student_key in item.student_deductions.get_graded_students():
                all_graded_students.add(student_key)

        print("")
        print("=" * 60)
        print_color(TermColors.GREEN, "All students have been graded!")
        print("=" * 60)
        print("")

        # Show summary
        print(fpad2 + f"Total students graded: {len(all_graded_students)}")
        print("")

        # Show menu
        menu_items = [
            (MenuCommand.MANAGE_GRADES, "Manage grades (view/delete student grades)"),
            (MenuCommand.DELETE_DEDUCTION, "Delete deduction type"),
            (MenuCommand.CHANGE_VALUE, "Change deduction value"),
            (MenuCommand.EXIT, "Exit grader"),
        ]
        print(fpad2 + "Options:")
        for cmd, desc in menu_items:
            _print_menu_item(cmd, desc, fpad2)
        print("")

        txt = input(TermColors.BLUE + ">>> " + TermColors.END).strip().lower()

        if txt == MenuCommand.MANAGE_GRADES.value:
            if _manage_grades_interactive(items, names_by_netid):
                # A grade was deleted, signal caller to re-run grading
                return True
        elif txt == MenuCommand.DELETE_DEDUCTION.value:
            selected_item = _select_item_interactive(
                items, "delete deduction type from"
            )
            if selected_item:
                selected_item.student_deductions.delete_deduction_type_interactive()
        elif txt == MenuCommand.CHANGE_VALUE.value:
            selected_item = _select_item_interactive(
                items, "change deduction value for"
            )
            if selected_item:
                selected_item.student_deductions.change_deduction_value_interactive(
                    max_points=selected_item.max_points
                )
        elif txt == MenuCommand.EXIT.value:
            print_color(TermColors.BLUE, "Exiting grader")
            sys.exit(0)
        else:
            print_color(TermColors.YELLOW, "Invalid option. Try again.")


def _select_item_interactive(items, action_description):
    """Prompt user to select an item when there are multiple items.

    Args:
        items: List of GradeItem objects
        action_description: String describing the action (e.g., "delete deduction type from")

    Returns:
        Selected GradeItem, or None if cancelled
    """
    if len(items) == 1:
        return items[0]

    print(f"\nSelect which item to {action_description}:")
    for i, item in enumerate(items, 1):
        print(f"  [{i}] {item.item_name}")
    print("  [Enter] Cancel")

    txt = input("\n>>> ").strip()
    if txt == "":
        return None

    try:
        idx = int(txt) - 1
        if 0 <= idx < len(items):
            return items[idx]
        print_color(TermColors.YELLOW, "Invalid selection.")
        return None
    except ValueError:
        print_color(TermColors.YELLOW, "Invalid input.")
        return None


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
    all_items=None,
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
        all_items: List of all GradeItem objects (for multi-item operations like [g], [d], [v])

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
            for deduction in current_deductions:
                print(fpad2 + f"  -{deduction.points}: {deduction.message}")
        else:
            print(fpad2 + "  (None)")
        print("")

        ################### Build input menu #######################
        # Build menu items for two-column display
        # Each item is (MenuCommand or None, description) - None for special items like [Enter]
        left_items = [
            (MenuCommand.SKIP, "Skip student"),
        ]
        if allow_rebuild:
            left_items.append((MenuCommand.BUILD, "Build & run"))
        if allow_rerun:
            desc = "Re-run" if not allow_rebuild else "Re-run (no build)"
            left_items.append((MenuCommand.RERUN, desc))
        left_items.append((MenuCommand.MANAGE_GRADES, "Manage grades"))
        if last_graded_net_ids is not None:
            left_items.append((MenuCommand.UNDO, f"Undo last ({last_graded_net_ids[0]})"))
        left_items.append((MenuCommand.EXIT, "Exit grader"))

        right_items = [
            (MenuCommand.NEW_DEDUCTION, "New deduction"),
            (MenuCommand.DELETE_DEDUCTION, "Delete deduction"),
            (MenuCommand.CLEAR_DEDUCTIONS, "Clear deductions"),
            (MenuCommand.CHANGE_VALUE, "Change deduction value"),
            (None, "Accept score"),  # [Enter] - special case
        ]

        # Build allowed_cmds from menu items
        allowed_cmds = {}
        for cmd, _ in left_items + right_items:
            if cmd is not None:
                allowed_cmds[cmd.value] = cmd

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
                cmd, desc = left_items[i]
                key_str = cmd.key_display if cmd else "[Enter]"
                col1 = (
                    fpad2 + TermColors.BLUE + key_str.ljust(pad) + TermColors.END + desc
                )
                # Pad to column width (accounting for ANSI codes)
                col1_visible_len = len(fpad2) + len(key_str.ljust(pad)) + len(desc)
                col1_padded = col1 + " " * (col_width - col1_visible_len)
            else:
                col1_padded = " " * col_width

            # Right column
            if i < len(right_items):
                cmd, desc = right_items[i]
                key_str = cmd.key_display if cmd else "[Enter]"
                col2 = TermColors.BLUE + key_str.ljust(pad) + TermColors.END + desc
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
            cmd = allowed_cmds[txt]

            # Handle special cases that need to loop back
            if cmd == MenuCommand.NEW_DEDUCTION:
                deduction_id = student_deductions.create_deduction_type_interactive(
                    max_points=max_points
                )
                if deduction_id >= 0:
                    # Auto-apply the new deduction to this student
                    student_deductions.apply_deduction_to_student(
                        tuple(net_ids), deduction_id
                    )
                continue
            if cmd == MenuCommand.DELETE_DEDUCTION:
                if all_items and len(all_items) > 1:
                    selected_item = _select_item_interactive(
                        all_items, "delete deduction type from"
                    )
                    if selected_item:
                        selected_item.student_deductions.delete_deduction_type_interactive()
                else:
                    student_deductions.delete_deduction_type_interactive()
                continue
            if cmd == MenuCommand.CHANGE_VALUE:
                if all_items and len(all_items) > 1:
                    selected_item = _select_item_interactive(
                        all_items, "change deduction value for"
                    )
                    if selected_item:
                        selected_item.student_deductions.change_deduction_value_interactive(
                            max_points=selected_item.max_points
                        )
                else:
                    student_deductions.change_deduction_value_interactive(
                        max_points=max_points
                    )
                continue
            if cmd == MenuCommand.MANAGE_GRADES:
                if all_items:
                    _manage_grades_interactive(all_items, names_by_netid)
                else:
                    # Fallback for single item - wrap in list
                    # Create a minimal item-like object for backwards compatibility
                    class _SingleItemWrapper:
                        def __init__(self, student_deductions_arg):
                            self.student_deductions = student_deductions_arg

                    _manage_grades_interactive(
                        [_SingleItemWrapper(student_deductions)], names_by_netid
                    )
                continue

            # Commands that return directly (SKIP, BUILD, RERUN, UNDO, EXIT)
            return cmd

        # Check for clear command (must be exactly "0", not in a list)
        if txt == MenuCommand.CLEAR_DEDUCTIONS.value:
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


def _manage_grades_interactive(all_items, names_by_netid=None):
    """Interactive menu to manage (view/delete) grades for any student.

    Args:
        all_items: List of GradeItem objects (to access their student_deductions)
        names_by_netid: Dict mapping net_id -> (first_name, last_name) for search

    Returns:
        True if a grade was deleted, False otherwise
    """
    while True:
        # Collect graded students from ALL items
        all_graded_students = set()
        for item in all_items:
            for student_key in item.student_deductions.get_graded_students():
                all_graded_students.add(student_key)

        print("\n" + "=" * 60)
        print_color(TermColors.BLUE, "Manage Grades")
        print("=" * 60)

        if not all_graded_students:
            print("No students have been graded yet.")
            input("Press Enter to continue...")
            return False

        print(f"{len(all_graded_students)} student(s) graded.")
        print("\nOptions:")
        print("  [search]  Enter search string to find student by name or net_id")
        print("  [*]       List all graded students")
        print("  [Enter]   Return to grading")

        txt = input("\nSearch: ").strip()

        if txt == "":
            return False

        # Check for wildcard to list all
        list_all = txt == "*"

        # Search for matching students (case-insensitive)
        search_lower = txt.lower()
        matches = []

        for net_ids in all_graded_students:
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
        # Show combined deduction info from all items
        print(f"\nFound {len(matches)} match(es):")
        for i, (net_ids, display) in enumerate(matches, 1):
            total_deductions = 0
            total_items_graded = 0
            total_deduction_count = 0
            for item in all_items:
                if item.student_deductions.is_student_graded(net_ids):
                    total_items_graded += 1
                    total_deductions += item.student_deductions.total_deductions(
                        net_ids
                    )
                    total_deduction_count += len(
                        item.student_deductions.get_student_deductions(net_ids)
                    )
            # Format differently based on single vs multiple items
            if len(all_items) == 1:
                print(
                    f"  [{i}] {display} "
                    f"({total_deduction_count} deduction(s), -{total_deductions} pts)"
                )
            else:
                print(
                    f"  [{i}] {display} "
                    f"(graded in {total_items_graded} item(s), -{total_deductions} pts total)"
                )

        print("\n  [#]      Enter number to delete that student's grade")
        print("  [Enter]  Cancel")

        choice = input("\n>>> ").strip()

        if choice == "":
            return False

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(matches):
                student_key, display = matches[idx]
                # Confirm deletion
                confirm = (
                    input(
                        f"Delete grade for {display} from ALL items? This cannot be undone. [y/N]: "
                    )
                    .strip()
                    .lower()
                )

                if confirm == "y":
                    # Delete from ALL items
                    for item in all_items:
                        item.student_deductions.clear_student_deductions(student_key)
                    print_color(
                        TermColors.GREEN, f"Deleted grade for {display} from all items"
                    )
                    return True  # Signal that a grade was deleted
                print("Cancelled.")
            else:
                print_color(TermColors.YELLOW, "Invalid selection.")
        except ValueError:
            print_color(TermColors.YELLOW, "Invalid input.")
