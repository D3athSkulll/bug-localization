# Faculty demo (PowerShell). Run from repo root:  .\scripts\run\demo.ps1
. "$PSScriptRoot\..\setup\env.ps1"
Set-Location $ROOT
Write-Host "`n== Pinned repos ==" -ForegroundColor Cyan
"Defects4J tag : " + (git -C defects4j describe --tags)
"buglocalization: " + (git -C buglocalization log -1 --oneline)
Write-Host "`n== Toolchain ==" -ForegroundColor Cyan
java -version
python --version
& "$ROOT\envs\modern312\Scripts\python.exe" --version
Write-Host "`n== Bug Lang-1 (Defects4J commit-db) and its bug report ==" -ForegroundColor Cyan
(Get-Content defects4j\framework\projects\Lang\commit-db -TotalCount 1)
python -c "import json;d=json.load(open('data/bug_reports/Lang-1.json'));print(d['fields']['summary']);print(d['fields']['description'][:300])"
Write-Host "`n== Checkout + compile + run tests (expect 1 error: TestLang747) ==" -ForegroundColor Cyan
& "C:\Program Files\Git\bin\bash.exe" scripts/run/smoke_lang1.sh
Write-Host "`n== Defects4J's recorded trigger failure for Lang-1 ==" -ForegroundColor Cyan
Get-Content defects4j\framework\projects\Lang\trigger_tests\1 -TotalCount 2
Write-Host "`n== Unit tests (104) ==" -ForegroundColor Cyan
python -m pytest -q tests
Write-Host "`n== ISBL baseline on Lang-1: IR -> top-k -> spectrum -> Ochiai/DStar -> metrics ==" -ForegroundColor Cyan
python -m isbl.baseline.pipeline configs\lang1_k50.json --recollect --explain
