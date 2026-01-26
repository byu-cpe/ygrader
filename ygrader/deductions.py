"""
Deduction system for student assignments.
"""

import pathlib
from typing import List, Optional

import yaml

from .utils import TermColors, print_color


class FlowList(list):
    """A list subclass that will be serialized in YAML flow style (inline)."""


def flow_list_representer(dumper, data):
    """Custom YAML representer for FlowList to use flow style."""
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


yaml.add_representer(FlowList, flow_list_representer)


class DeductionType:
    """A reusable deduction type that can be applied across multiple students."""

    message: str
    points: float = 0.0

    def __init__(self, message: str, points: float = 0.0):
        self.message = message
        self.points = points

    def __str__(self) -> str:
        """String representation of the deduction type."""
        if self.points != 0:
            return f"{self.message} ({self.points:+.1f} points)"
        return self.message


class StudentDeductions:
    """Collection of all deductions for students."""

    def __init__(self, yaml_path: Optional[pathlib.Path] = None):
        self.deductions_by_students = {}
        self.submit_time_by_students = {}  # ISO format timestamp strings
        self.deduction_types = {}
        self.yaml_path = yaml_path

        # Load from YAML file if it exists
        if yaml_path is not None and yaml_path.is_file():
            self._load_from_yaml()

    def _save(self):
        """Save the current state to YAML file if a path is set."""
        if self.yaml_path is not None:
            self._write_yaml()

    def _load_from_yaml(self):
        """Load deduction types and student deductions from the YAML file.

        Expected YAML structure:
        deduction_types:
          - id: 0
            desc: Deduction description
            points: 5

        student_deductions:
          - net_ids: ["idA", "idB"]
            deductions: [0, 3]
        """
        assert self.yaml_path.exists(), f"YAML file {self.yaml_path} does not exist."

        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Load deduction types if present
        if data and "deduction_types" in data:
            for deduction in data["deduction_types"]:
                deduction_id = deduction["id"]
                desc = deduction["desc"]
                points = deduction["points"]

                # Create a DeductionType for this deduction
                deduction_type = DeductionType(message=desc, points=points)
                self.deduction_types[deduction_id] = deduction_type

        # Load student deductions if present
        if data and "student_deductions" in data:
            for entry in data["student_deductions"]:
                net_ids = entry["net_ids"]
                deduction_ids = entry["deductions"]

                # Use tuple of net_ids as the key
                student_key = tuple(net_ids)
                deduction_items = []

                for deduction_id in deduction_ids:
                    if deduction_id in self.deduction_types:
                        deduction_items.append(self.deduction_types[deduction_id])

                self.deductions_by_students[student_key] = deduction_items

                # Load submit_time if present
                if "submit_time" in entry:
                    self.submit_time_by_students[student_key] = entry["submit_time"]

    def _write_yaml(self):
        """Write deduction types and student deductions to the YAML file.

        Writes in the format:
        deduction_types:
          - id: 0
            desc: Deduction description
            points: 5

        student_deductions:
          - net_ids: ["idA", "idB"]
            deductions: [0, 3]
        """
        data = {}

        # Write deduction types
        if self.deduction_types:
            deduction_list = []
            for deduction_id, deduction_type in self.deduction_types.items():
                deduction_list.append(
                    {
                        "id": deduction_id,
                        "desc": deduction_type.message,
                        "points": deduction_type.points,
                    }
                )
            data["deduction_types"] = deduction_list

        # Write student deductions (include students with deductions OR submit_time)
        all_student_keys = set(self.deductions_by_students.keys()) | set(
            self.submit_time_by_students.keys()
        )
        # Sort student keys for consistent output ordering
        sorted_student_keys = sorted(all_student_keys)
        if sorted_student_keys:
            student_deduction_list = []
            for student_key in sorted_student_keys:
                deduction_items = self.deductions_by_students.get(student_key, [])
                # Find the deduction IDs for these deduction items
                deduction_ids = []
                for deduction_item in deduction_items:
                    # Find the ID of this deduction item in deduction_types
                    for deduction_id, dt_item in self.deduction_types.items():
                        if dt_item is deduction_item:
                            deduction_ids.append(deduction_id)
                            break

                student_deduction_list.append(
                    {
                        "net_ids": FlowList(student_key),
                        "deductions": FlowList(deduction_ids),
                        **(
                            {"submit_time": self.submit_time_by_students[student_key]}
                            if student_key in self.submit_time_by_students
                            else {}
                        ),
                    }
                )
            data["student_deductions"] = student_deduction_list

        # Create parent directory if it doesn't exist
        self.yaml_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def add_deduction_type(self, message: str, points: float = 0.0) -> int:
        """Add a new deduction type.

        Args:
            message: The deduction message/description
            points: Points to deduct (must be non-negative)

        Returns:
            The ID assigned to this deduction type
        """
        if points < 0:
            raise ValueError(f"Deduction points must be non-negative, got {points}")
        # Find the next available ID (start at 1, reserve 0 for clear command)
        if self.deduction_types:
            next_id = max(self.deduction_types.keys()) + 1
        else:
            next_id = 1

        # Create and store the deduction type
        deduction_type = DeductionType(message=message, points=points)
        self.deduction_types[next_id] = deduction_type

        self._save()
        return next_id

    def find_or_create_deduction_type(self, message: str, points: float = 0.0) -> int:
        """Find an existing deduction type by message, or create a new one if not found.

        Args:
            message: The deduction message/description to find or create
            points: Points to deduct (used only if creating a new type)

        Returns:
            The ID of the existing or newly created deduction type
        """
        # Search for existing deduction type with matching message
        for deduction_id, deduction_type in self.deduction_types.items():
            if deduction_type.message == message:
                return deduction_id

        # Not found, create a new one
        return self.add_deduction_type(message, points)

    def create_deduction_type_interactive(
        self, max_points: Optional[float] = None
    ) -> int:
        """Interactively prompt the user to create a new deduction type.

        Args:
            max_points: Optional maximum points for validation.

        Returns:
            The ID of the created deduction type, or -1 if cancelled.
        """
        print("\nCreate new deduction type (empty input to cancel):")

        # Prompt for description
        description = input("  Description: ").strip()
        if not description:
            print("Cancelled.")
            return -1

        # Prompt for points
        while True:
            points_str = input("  Points to deduct: ").strip()
            if not points_str:
                print("Cancelled.")
                return -1
            try:
                points = float(points_str)
                if points < 0:
                    print_color(
                        TermColors.YELLOW,
                        "Deduction cannot be negative. Try again.",
                    )
                    continue
                if max_points is not None and points > max_points:
                    print_color(
                        TermColors.YELLOW,
                        f"Deduction ({points}) cannot exceed max points ({max_points}). Try again.",
                    )
                    continue
                break
            except ValueError:
                print("Invalid number. Try again.")

        # Add the new deduction type
        deduction_id = self.add_deduction_type(description, points)
        print(
            f"Created deduction type [{deduction_id}]: {description} ({points} points)"
        )

        return deduction_id

    def is_deduction_in_use(self, deduction_id: int) -> bool:
        """Check if a deduction type is currently applied to any student.

        Args:
            deduction_id: The ID of the deduction type to check.

        Returns:
            True if any student has this deduction, False otherwise.
        """
        if deduction_id not in self.deduction_types:
            return False

        deduction_type = self.deduction_types[deduction_id]
        for student_deductions in self.deductions_by_students.values():
            if deduction_type in student_deductions:
                return True
        return False

    def delete_deduction_type(self, deduction_id: int) -> bool:
        """Delete a deduction type if it's not in use by any student.

        Args:
            deduction_id: The ID of the deduction type to delete.

        Returns:
            True if deleted successfully, False if in use or not found.
        """
        if deduction_id not in self.deduction_types:
            return False

        if self.is_deduction_in_use(deduction_id):
            return False

        del self.deduction_types[deduction_id]
        self._save()
        return True

    def delete_deduction_type_interactive(self) -> bool:
        """Interactively prompt the user to delete a deduction type.

        Returns:
            True if a deduction was deleted, False otherwise.
        """
        if not self.deduction_types:
            print("No deduction types to delete.")
            return False

        print("\nDelete deduction type (empty input to cancel):")
        print("Available deduction types:")
        for deduction_id, deduction_type in self.deduction_types.items():
            in_use = " (IN USE)" if self.is_deduction_in_use(deduction_id) else ""
            print(
                f"  [{deduction_id}] -{deduction_type.points}: {deduction_type.message}{in_use}"
            )

        id_str = input("  Enter ID to delete: ").strip()
        if not id_str:
            print("Cancelled.")
            return False

        try:
            deduction_id = int(id_str)
        except ValueError:
            print("Invalid ID.")
            return False

        if deduction_id not in self.deduction_types:
            print("Deduction type not found.")
            return False

        if self.is_deduction_in_use(deduction_id):
            print_color(
                TermColors.YELLOW,
                "Cannot delete - deduction is in use by one or more students.",
            )
            return False

        deduction_type = self.deduction_types[deduction_id]
        self.delete_deduction_type(deduction_id)
        print(f"Deleted deduction type [{deduction_id}]: {deduction_type.message}")
        return True

    def change_deduction_value(self, deduction_id: int, new_points: float) -> bool:
        """Change the point value of an existing deduction type.

        Args:
            deduction_id: The ID of the deduction type to modify.
            new_points: The new point value.

        Returns:
            True if successful, False if deduction_id not found.
        """
        if deduction_id not in self.deduction_types:
            return False

        self.deduction_types[deduction_id].points = new_points
        self._save()
        return True

    def change_deduction_value_interactive(
        self, max_points: Optional[float] = None
    ) -> bool:
        """Interactively prompt the user to change a deduction type's point value.

        Args:
            max_points: Optional maximum points for validation.

        Returns:
            True if a deduction value was changed, False otherwise.
        """
        if not self.deduction_types:
            print("No deduction types to modify.")
            return False

        print("\nChange deduction value (empty input to cancel):")
        print("Available deduction types:")
        for deduction_id, deduction_type in self.deduction_types.items():
            in_use = " (IN USE)" if self.is_deduction_in_use(deduction_id) else ""
            print(
                f"  [{deduction_id}] -{deduction_type.points}: {deduction_type.message}{in_use}"
            )

        id_str = input("  Enter ID to modify: ").strip()
        if not id_str:
            print("Cancelled.")
            return False

        try:
            deduction_id = int(id_str)
        except ValueError:
            print("Invalid ID.")
            return False

        if deduction_id not in self.deduction_types:
            print("Deduction type not found.")
            return False

        deduction_type = self.deduction_types[deduction_id]
        print(f"  Current value: {deduction_type.points} points")

        while True:
            points_str = input("  Enter new points value: ").strip()
            if not points_str:
                print("Cancelled.")
                return False

            try:
                new_points = float(points_str)
                if new_points < 0:
                    print_color(
                        TermColors.YELLOW,
                        "Deduction cannot be negative. Try again.",
                    )
                    continue
                if max_points is not None and new_points > max_points:
                    print_color(
                        TermColors.YELLOW,
                        f"Deduction ({new_points}) cannot exceed max points ({max_points}). Try again.",
                    )
                    continue
                break
            except ValueError:
                print("Invalid number. Try again.")

        old_points = deduction_type.points
        self.change_deduction_value(deduction_id, new_points)
        print(
            f"Changed deduction [{deduction_id}] from {old_points} to {new_points} points"
        )
        return True

    def get_student_deductions(self, net_ids: tuple) -> List[DeductionType]:
        """Get the list of deductions applied to a student.

        Args:
            net_ids: Tuple of net_ids to look up.

        Returns:
            List of DeductionType objects applied to this student.
        """
        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        return self.deductions_by_students.get(student_key, [])

    def apply_deduction_to_student(self, net_ids: tuple, deduction_id: int) -> bool:
        """Apply a deduction type to a student.

        Args:
            net_ids: Tuple of net_ids for the student.
            deduction_id: The ID of the deduction type to apply.

        Returns:
            True if successful, False if deduction_id not found.
        """
        if deduction_id not in self.deduction_types:
            return False

        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        if student_key not in self.deductions_by_students:
            self.deductions_by_students[student_key] = []

        deduction_type = self.deduction_types[deduction_id]
        if deduction_type not in self.deductions_by_students[student_key]:
            self.deductions_by_students[student_key].append(deduction_type)
            self._save()

        return True

    def clear_student_deductions(self, net_ids: tuple):
        """Clear all deductions for a student.

        Args:
            net_ids: Tuple of net_ids for the student.
        """
        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        if student_key in self.deductions_by_students:
            del self.deductions_by_students[student_key]
        if student_key in self.submit_time_by_students:
            del self.submit_time_by_students[student_key]
        self._save()

    def ensure_student_in_file(self, net_ids: tuple):
        """Ensure a student is in the deductions file, even with no deductions.

        This is used to indicate that a student has been graded (with a perfect score)
        rather than being absent from the file (not yet graded).

        Args:
            net_ids: Tuple of net_ids for the student.
        """
        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        if student_key not in self.deductions_by_students:
            self.deductions_by_students[student_key] = []
            self._save()

    def is_student_graded(self, net_ids: tuple) -> bool:
        """Check if a student has been graded (is in the deductions file).

        Args:
            net_ids: Tuple of net_ids for the student.

        Returns:
            True if the student is in the deductions file (graded), False otherwise.
        """
        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        return student_key in self.deductions_by_students

    def set_submit_time(self, net_ids: tuple, submit_time: Optional[str]):
        """Set the submission time for a student.

        Args:
            net_ids: Tuple of net_ids for the student.
            submit_time: ISO format timestamp string, or None to remove.
        """
        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        if submit_time:
            self.submit_time_by_students[student_key] = submit_time
        elif student_key in self.submit_time_by_students:
            del self.submit_time_by_students[student_key]
        self._save()

    def get_submit_time(self, net_ids: tuple) -> Optional[str]:
        """Get the submission time for a student.

        Args:
            net_ids: Tuple of net_ids for the student.

        Returns:
            ISO format timestamp string, or None if not set.
        """
        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        return self.submit_time_by_students.get(student_key)

    def total_deductions(self, net_ids: Optional[tuple] = None) -> float:
        """Calculate the total deductions for a student or all students.

        Args:
            net_ids: Tuple of net_ids to look up. If None, returns 0.

        Returns:
            The total points deducted for the specified student(s).
        """
        if net_ids is None:
            return 0.0

        # Look up the student by their net_ids tuple
        student_key = tuple(net_ids) if not isinstance(net_ids, tuple) else net_ids
        deduction_items = self.deductions_by_students.get(student_key, [])

        return sum(item.points for item in deduction_items)

    def get_graded_students(self) -> List[tuple]:
        """Get a list of all graded students.

        Returns:
            List of net_id tuples for all students who have been graded.
        """
        return list(self.deductions_by_students.keys())

    def find_student_by_netid(self, netid: str) -> Optional[tuple]:
        """Find a student's full net_ids tuple by a single net_id.

        This is useful for finding group members when you only know one net_id.

        Args:
            netid: A single net_id to search for.

        Returns:
            The full net_ids tuple if found, None otherwise.
        """
        for student_key in self.deductions_by_students:
            if netid in student_key:
                return student_key
        return None
