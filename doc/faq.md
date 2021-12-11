
# FAQs

**Q: How do I do group grading**


**Q: Do you recommend creating a new dedicated repository for the class specific grading scripts? Or incorporate into a current lab solutions repository?**

A: Up to you.  I typically use separate grading and solutions repos.  I do this because I give TAs access to the grading repos (they commit grades to CSV files), but I don't typically give TAs access to our solution repository.

**Q: How do the TAs access the scripts to run? Do they just checkout your main library and then checkout the repository for the class specific scripts to run?**

A: My usual approach is to make this repo a submodule in your class-specific repo, so TAs would clone your class grade repo.  To get submodule code you need to run `git submodule init` and `git submodule update`, but I usually wrap these into a `make install` Makefile that also installs necessary packages.  (See [427 Install Makefile](https://github.com/byu-cpe/ecen427_grader/blob/master/Makefile)).

* Building takes a long time?
* Groups
* Analysis
* Multiple assignments
* Multiple grade files
* Change teams
* One script for every lab?
