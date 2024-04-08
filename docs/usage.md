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

The typical usage model is that you create your own grader repository for your class, and then use this package in your own grading scripts. This is demonstrated in the [ygrader-example](https://github.com/byu-cpe/ygrader-example) repository, which you may fork as a good starting point.  

I typically give TAs access to this grading repo, and put them in charge of both exporting CSVs from Learning Suite, and importing them after grading.

## Setup

1. Start by creating a *Grader* object where you assign a name to what you are grading and provide the path of a CSV file contains student grades (exported from LearningSuite).
    ```python
    grader = ygrader.Grader(lab_name = "lab1", grades_csv_path = "learning_suite/grades.csv")
    ```

1. Next, indicate what item(s) (i.e., columns from your CSV file) that you want to grade, and provide a callback function that you want to be run for each student's submission (this callback function is where you will run student's code, inspect their submitted files, etc).  You can optionally specify a maximum number of points that this item is out of.
    ```python
    grader.add_item_to_grade("lab1_grade", my_callback, max_points = 10)
    ```
1. Set the submission system to either:

    a. Learning Suite: In this case you need to provide the zip file from the *Batch Download* of submissions on LearningSuite.
    ```python
    grader.set_submission_system_learning_suite("learning_suite/lab1_submissions.zip")
    ```

    b. Github: In this case you need to provide a git tag/branch name that contains the student's submissions, as well as a CSV file that contains a list of student Net IDs and their github URL.
    ```python
    grader.set_submission_system_github("lab1_submission", "github_urls.csv")
    ```

1. (Optional) Provide groups for team-based assignments:
    ```python
    grader.set_learning_suite_groups("groups.csv")
    ```

1. (Optional) Set any optional arguments:
    ```python
    grader.set_other_options(format_code=True)
    ```

1. Run!
    ```python
    grader.run()
    ```