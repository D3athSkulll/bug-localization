from isbl.baseline import ir_models as M

TRACE = ("Test fails with this error\n"
         "java.lang.AssertionError: Expected: <x> but: was <y>\n"
         "\tat org.hamcrest.MatcherAssert.assertThat(MatcherAssert.java:20)\n"
         "\tat com.example.FooTest.test(FooTest.java:28)\n"
         "Caused by: java.io.IOException: boom\n"
         "\t... 12 more\n"
         "the real description continues here")


def test_strip_stack_traces_removes_frames_but_keeps_prose():
    out = M.strip_stack_traces(TRACE)
    assert "MatcherAssert" not in out and "FooTest" not in out and "12 more" not in out and "Caused by" not in out
    assert "Test fails with this error" in out and "real description continues here" in out
    assert "java.lang.AssertionError" in out                   # the exception line itself is ordinary prose


def test_strip_stack_traces_handles_empty_and_none():
    assert M.strip_stack_traces("") == ""
    assert M.strip_stack_traces(None) == ""
    assert M.strip_stack_traces("nothing to strip") == "nothing to strip"


def test_clean_query_option_changes_ranking_when_trace_is_noise():
    files = {"JavaVersion.java": "java org apache java org apache java", "LocaleUtils.java": "locale locale parse"}
    noisy = "locale parse fails\n" + "\tat org.apache.maven.Foo.run(Foo.java:1)\n" * 30
    dirty = [f for f, _ in M.rank("tf_cosine", noisy, files)]
    clean = [f for f, _ in M.rank("tf_cosine", noisy, files, clean_query=True)]
    assert dirty[0] == "JavaVersion.java"                      # noise terms (org, apache) win without cleaning
    assert clean[0] == "LocaleUtils.java"
