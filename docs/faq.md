
# FAQs

## Organization

**Q: Do you recommend creating a new dedicated repository for the class specific grading scripts? Or incorporate into a current lab solutions repository?**

A: Up to you.  I typically use separate grading and solutions repos.  I do this because I give TAs access to the grading repos (they commit grades to CSV files), but I don't typically give TAs access to our solution repository.

**Q: How do the TAs access the scripts to run? Do they just checkout your main library and then checkout the repository for the class specific scripts to run?**

A: My usual approach is to make this repo a submodule in your class-specific repo, so TAs would clone your class grade repo.  To get submodule code you need to run `git submodule init` and `git submodule update`, but I usually wrap these into a `make install` Makefile that also installs necessary packages.  (See [427 Install Makefile](https://github.com/byu-cpe/ecen427_grader/blob/master/Makefile)).


**Q: Should I export separate grades CSV files from Learning Suite for each lab, or one big CSV file?**

A: Either works.  It's easier to edit grades in smaller files, but quicker to import everything at once if you use one file.



## Teams/Group Assignments

**Q: Can do I do group grading**

A: Yes.  

For Github submissions, just make sure each group members has the same Github URL and they will automatically be formed into groups.

For Learning Suite submissions, use the `set_learning_suite_groups()` function to provide a CSV file indicating the group name of each students.


**Q: What if I have multiple team-based assignments and I have to change some team members between assignments?**

A: Keep your groups in a CSV file, and use one column for each assignment.  When you start a new assignment, just copy the first column and make any adjustments as needed for each assignment.  When you call `set_learning_suite_groups()` you can specify which column to use to form groups.

## Other Options
**Q: Grading each student takes a long time to compile/synthesize/simulate.  What should I do?**

A: You can call `set_other_options()` and set `build_only` to True.  Run the grader with this option set first, then run it again with `run_only` set to True.  This will set the `build` and `run` boolean arguments of your callback function appropriately.  

**Q: Can I grade multiple items for a student at once?**
A: Yes, you can grade multiple columns, and can control whether your callback is called for each column, or whether your callback is run once to determine grades for multiple columns (or a mix of these approaches).

For each columns(s) you want your callback function invoked, use a separate call to `add_item_to_grade`.  If you want to grade multiple columns per invocation of your callback, then provide a list of those column names to `add_item_to_grade`.
