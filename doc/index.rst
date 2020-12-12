Welcome to pygrader's documentation!
====================================

The package is designed to help you write grading scripts.  The main idea behind the package is that it removes all of the overhead that is common between grading different classes (extracing student code into their own folder, updating grade CSV files, etc), and allows you to focus on just writing scripts for running student code in your classes environment.

Grading Flow
############

When you configure the script correctly, the expected flow is:

1. Grade CSV from LearningSuite is parsed, and student grades are tracked in a pandas DataFrame
2. Students are filtered down to only those that still need a grade for the assignment.
3. Students are formed into their groups (groups of 1 for individual assignments)
4. For each student:

   * Student code is retrieved (from Github or Learning suite zip file) and copied into a per-group working folder.
   * *Callbacks are made to your code*, where you can build and run the student's code.
   * The grader is prompted to enter a grade.  They can optionally rebuild and rerun the students code, or skip to the next student without entering a grade.
   * Grade CSV is updated with grade for all group members.

In the above process, *you will only need to write the callback code to buil and run the users code*.


Major Features
##############
* The package can work with student code submitted via zip files (ie using Learning Suite), *or* with student code on Github.  
* Supports labs with multiple different grade columns in Learning Suite (referred to as *milestones* in this documentation).  This can allow you to run different tests each worth different number of points.
* Supports team-based assignments (currently via Github submission only).
* Grades are updated in the CSV files as soon as you enter them, meaning you can Ctrl+C the grading at any point, and re-run to continue where you left off.


Examples
########
* ECEN 330 grader: https://github.com/byu-cpe/ecen330_grader

  * https://github.com/byu-cpe/ecen330_grader/blob/master/run_passoff_grader.py
  * https://github.com/byu-cpe/ecen330_grader/blob/master/run_coding_standard_grader.py

* ECEN 427 grader: https://github.com/byu-cpe/ecen427_grader

  * https://github.com/byu-cpe/ecen427_grader/blob/master/run_passoff.py
  * https://github.com/byu-cpe/ecen427_grader/blob/master/run_coding_standard.py

Class Documentation
###################


.. automodule:: pygrader.grader
   :members:

