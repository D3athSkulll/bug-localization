# Demo of the improvement experiments on Lang-1, Lang-2, Lang-3 (about 1 minute). Run from anywhere:
#   .\scripts\run\demo_experiments.ps1
. "$PSScriptRoot\..\setup\env.ps1"
Set-Location $ROOT
Write-Host "`n== 1. Cosine audit: is the cosine similarity implemented correctly, and why does the wrong file win? ==" -ForegroundColor Cyan
python scripts\run\cosine_audit.py
Write-Host "`n== 2. Unit tests ==" -ForegroundColor Cyan
python -m pytest -q tests
Write-Host "`n== 3. IR models x SFL formulas x ISBL x hybrid ranking on Lang-1/2/3 ==" -ForegroundColor Cyan
python scripts\run\run_experiments.py 2>$null
Write-Host "`nTables: results\experiments\*.csv   Excel: .\results\Lang-1-2-3_experiments.xlsx" -ForegroundColor Green
