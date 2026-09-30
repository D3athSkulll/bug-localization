# source this (Git Bash): activates JDK 8 + legacy Python 3.7 for the historical reproduction
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export JAVA_HOME="$(cd "$ROOT/tools/jdk8u504-b01" && pwd -W)"
export PATH="$ROOT/tools/jdk8u504-b01/bin:$ROOT/envs/legacy37:$ROOT/envs/legacy37/Library/bin:$ROOT/envs/legacy37/Scripts:$PATH"
