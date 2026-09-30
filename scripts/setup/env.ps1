# dot-source in PowerShell:  . .\scripts\setup\env.ps1
$ROOT = (Resolve-Path "$PSScriptRoot\..\..").Path
$env:JAVA_HOME = "$ROOT\tools\jdk8u504-b01"
$env:PATH = "$ROOT\tools\jdk8u504-b01\bin;$ROOT\envs\legacy37;$ROOT\envs\legacy37\Library\bin;$ROOT\envs\legacy37\Scripts;$env:PATH"
