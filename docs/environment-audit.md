# Environment audit (2026-09-30)
Machine: Windows 11 Home 10.0.26200, NVIDIA RTX 2050 4GB, 24GB free on C:. Not admin. Native Windows used; WSL (Ubuntu, WSL2) present but NOT used.
Pre-existing: git 2.49, Python 3.9/3.11/3.12/3.14, conda, Maven 3.9.9, Git-for-Windows perl 5.38.2 (msys). Missing: Java, SVN, wget, Ant.
**The three repos the prompt says were cloned did not exist.** Created from public sources:
- buglocalization = github.com/Naplues/buglocalization @ bbd67ea6 (2018). Contains BugLocator Java source (+lucene jars), Perl/Python VSM scripts, Eclipse/AspectJ/SWT/JDT/Tomcat/Birt datasets. It contains NO Defects4J / ISBL / Ochiai code. Assumption: this is the intended repo - unconfirmed.
- defects4j = rjust/defects4j tag v1.4.0 @ fcf6b9bb (detached HEAD).
- BugLocator: no separate repo; the copy inside buglocalization/BugLocator is used.
Compatibility problems: (1) d4j 1.4.0 init.sh downloads from people.cs.umass.edu -> 404 (repos archive gone); (2) d4j is Perl+bash+SVN, Perl DBI/DBD::CSV not installed and no SVN, so the d4j CLI was not run; (3) d4j 1.x targets Java 7, javac 8 fails on TypeUtilsTest (generics inference).
Proposed: JDK8 portable + conda py3.7 (legacy) + py3.12 venv (modern). Unresolved: d4j CLI on Windows, SVN, coverage tool, full 6-project repo set, Java 7.
