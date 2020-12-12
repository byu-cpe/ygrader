Welcome to pygrader's documentation!
====================================

The package is designed to help you write grading scripts.  The main idea behind the package is that it processes grade CSV files exported from LearningSuite, detects which students still needs grading for an assignment, makes callbacks to your code for lab-specific build and run functions, and then asks you to enter a grade, which is automatically entered into the CSV file.  

Major feature:

* The package can work with student code submitted via zip files (ie using Learning Suite), *or* with student code on Github.  
* Supports labs with multiple different grade columns in Learning Suite (referred to as *milestones* in this documentation).  This can allow you to run different tests each worth different number of points.
* Supports team-based assignments (currently via Github submission only).
* Grades are updated in the CSV files as soon as you enter them, meaning you can Ctrl+C the grading at any point, and re-run to continue where you left off.

.. automodule:: pygrader.grader
   :members:

