"""
Feedback system for student assignments.
"""

from dataclasses import dataclass, field
import pathlib
from typing import List, Optional

import yaml


class FeedbackItem:
    """A reusable feedback item that can be applied across multiple students."""

    message: str
    points_deducted: float = 0.0

    def __init__(self, message: str, points_deducted: float = 0.0):
        self.message = message
        self.points_deducted = points_deducted

    def __str__(self) -> str:
        """String representation of the feedback item."""
        if self.points_deducted != 0:
            return f"{self.message} ({self.points_deducted:+.1f} points)"
        return self.message


class StudentFeedback:
    """Collection of all feedback for a student."""

    def __init__(self):
        self.feedback_by_students = {}
        self.deduction_types = {}

    def load_from_yaml(self, yaml_path: pathlib.Path):
        """Load deduction types and student deductions from a YAML file.

        Expected YAML structure:
        deduction_types:
          - id: 0
            desc: Deduction description
            points: 5

        student_deductions:
          - net_ids: ["idA", "idB"]
            deductions: [0, 3]
        """
        assert yaml_path.exists(), f"YAML file {yaml_path} does not exist."

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        # Load deduction types if present
        if data and "deduction_types" in data:
            for deduction in data["deduction_types"]:
                deduction_id = deduction["id"]
                desc = deduction["desc"]
                points = deduction["points"]

                # Create a FeedbackItem for this deduction type
                feedback_item = FeedbackItem(message=desc, points_deducted=points)
                self.deduction_types[deduction_id] = feedback_item

        # Load student deductions if present
        if data and "student_deductions" in data:
            for entry in data["student_deductions"]:
                net_ids = entry["net_ids"]
                deduction_ids = entry["deductions"]

                # Use tuple of net_ids as the key
                student_key = tuple(net_ids)
                feedback_items = []

                for deduction_id in deduction_ids:
                    if deduction_id in self.deduction_types:
                        feedback_items.append(self.deduction_types[deduction_id])

                self.feedback_by_students[student_key] = feedback_items

    def write_yaml(self, yaml_path: pathlib.Path):
        """Write deduction types and student deductions to a YAML file.

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
            for deduction_id, feedback_item in self.deduction_types.items():
                deduction_list.append(
                    {
                        "id": deduction_id,
                        "desc": feedback_item.message,
                        "points": feedback_item.points_deducted,
                    }
                )
            data["deduction_types"] = deduction_list

        # Write student deductions
        if self.feedback_by_students:
            student_deduction_list = []
            for student_key, feedback_items in self.feedback_by_students.items():
                # Find the deduction IDs for these feedback items
                deduction_ids = []
                for feedback_item in feedback_items:
                    # Find the ID of this feedback item in deduction_types
                    for deduction_id, dt_item in self.deduction_types.items():
                        if dt_item is feedback_item:
                            deduction_ids.append(deduction_id)
                            break

                student_deduction_list.append(
                    {"net_ids": list(student_key), "deductions": deduction_ids}
                )
            data["student_deductions"] = student_deduction_list

        # Write to file
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def add_feedback_item(self, message: str, points: float = 0.0) -> int:
        """Add a new feedback item to the deduction types.

        Args:
            message: The feedback message/description
            points: Points to deduct (can be negative for bonus points)

        Returns:
            The ID assigned to this feedback item
        """
        # Find the next available ID
        if self.deduction_types:
            next_id = max(self.deduction_types.keys()) + 1
        else:
            next_id = 0

        # Create and store the feedback item
        feedback_item = FeedbackItem(message=message, points_deducted=points)
        self.deduction_types[next_id] = feedback_item

        return next_id
