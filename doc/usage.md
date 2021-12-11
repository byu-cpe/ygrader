# Usage

## Grading Flow

When you configure the script correctly, the expected flow is:

1. Grade CSV from LearningSuite is parsed, and student grades are tracked in a pandas DataFrame
1. Students are filtered down to only those that still need a grade for the assignment.
1. Students are formed into their groups (groups of 1 for individual assignments)
1. For each student:

   * Student code is retrieved (from Github or Learning suite zip file) and copied into a per-group working folder.
   * *Callbacks are made to your code*, where you can build and run the student's code.
   * The TA is prompted to enter a grade.  They can optionally rebuild and rerun the students code, or skip to the next student without entering a grade.
   * Grade CSV is updated with grade for all group members.

In the above process, *you will only need to write the callback code to build and run the student's code*.

## File Organization


The typical usage model is that you create your own grader repository for your class, and would add this repository as a submodule. This is demonstrated in the [pygrader-example](https://github.com/byu-cpe/pygrader-example) repository, which you may fork as a good starting point.  

I typically give TAs access to this grading repo, and put them in charge of both exporting CSVs from Learning Suite, and importing them after grading.
