
# FAQs


**Q: Do you recommend creating a new dedicated repository for the class specific grading scripts? Or incorporate into a current lab solutions repository?**

A: Up to you.  I typically use separate grading and solutions repos.  I do this because I give TAs access to the grading repos (they commit grades to CSV files), but I don't typically give TAs access to our solution repository.

**Q: How do the TAs access the scripts to run? Do they just checkout your main library and then checkout the repository for the class specific scripts to run?**

A: My usual approach is to make this repo a submodule in your class-specific repo, so TAs would clone your class grade repo.  To get submodule code you need to run `git submodule init` and `git submodule update`, but I usually wrap these into a `make install` Makefile that also installs necessary packages.  (See [427 Install Makefile](https://github.com/byu-cpe/ecen427_grader/blob/master/Makefile)).

**Q: Grading each student takes a long time to compile/synthesize/simulate.  What should I do?**

A: You can call `set_other_options()` and set `build_only` to True.  Run the grader with this option set first, then run it again with `run_only` set to True.  This will set the `build` and `run` boolean arguments of your callback function appropriately.

**Q: Can I grade multiple items for a student at once?**

A: Yes, when you initialize the *Grader* class, provide a list into the *grades_col_name* argument of all of the columns you want to grade.  Your callback will be run for each item.  The *points* argument also needs to be a list of the same length indicating the maximum number of points possible for each item.

**Q: Should I export separate grades CSV files from Learning Suite for each lab, or one big CSV file?**

A: Either works.  It's easier to edit grades in smaller files, but quicker to import everything at once if you use one file.

**Q: Can do I do group grading**

A: Yes.  

For Github submissions, just make sure each group members has the same Github URL and they will automatically be formed into groups.

For Learning Suite submissions, use the `set_learning_suite_groups()` function to provide a CSV file indicating the group name of each students.


**Q: What if I have multiple team-based assignments and I have to change some team members between assignments?**

A: Keep your groups in a CSV file, and use one column for each assignment.  When you start a new assignment, just copy the first column and make any adjustments as needed for each assignment.  
