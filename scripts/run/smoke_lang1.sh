#!/usr/bin/env bash
# Smoke test: Defects4J Lang-1 (buggy src + fixed-commit tests) on Windows, JDK 8, Maven.
# Mirrors Defects4J v1.4.0 commit-db; hashes are remapped to apache/commons-lang GitHub history
# because the legacy d4j repo archive host returns 404.
set -e
source "$(dirname "$0")/../setup/env.sh"
cd "$ROOT"
[ -d work-lang ] || git clone https://github.com/apache/commons-lang.git work-lang
cd work-lang
git checkout -q 396afc3e4693cfee182efe582455f2d97058c068                  # buggy
git checkout -q d1a45e9738de5b3e299bb51e987565dcce55fee6 -- src/test/java/org/apache/commons/lang3/math/NumberUtilsTest.java  # fixed tests
mkdir -p ../data; [ -f src/test/java/org/apache/commons/lang3/reflect/TypeUtilsTest.java ] && mv src/test/java/org/apache/commons/lang3/reflect/TypeUtilsTest.java ../data/TypeUtilsTest.java.excluded  # javac8 generics incompat
mvn -B -q -DskipTests compile
mvn -B -Dtest=NumberUtilsTest -DfailIfNoTests=false test | grep -E "Tests run:|TestLang747|BUILD" || true
