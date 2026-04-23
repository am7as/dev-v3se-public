<#
    .SYNOPSIS
        One-shot bootstrap for the v3se-templates scaffold.

    .DESCRIPTION
        Substitutes three placeholder tokens across the tree:
            __PACKAGE_NAME__         Python identifier (snake_case)
            __PROJECT_SLUG__         display / workspace name (kebab-case)
            __PROJECT_DESCRIPTION__  free-form one-liner

        Renames src/__PACKAGE_NAME__/ to src/<real-name>/ and deletes
        both instantiate scripts at the end.

    .EXAMPLE
        .\scripts\instantiate.ps1
        (interactive mode; prompts for all three values)

    .EXAMPLE
        .\scripts\instantiate.ps1 `
            -PackageName crash_survey `
            -Slug crash-survey `
            -Description "Survey of crashes"
#>

[CmdletBinding()]
param(
    [string]$PackageName,
    [string]$Slug,
    [string]$Description
)

$ErrorActionPreference = 'Stop'

# --- locate template root ---
$ScriptDir    = Split-Path -Parent $PSCommandPath
$TemplateRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path

function Die([string]$msg) {
    Write-Host "error: $msg" -ForegroundColor Red
    exit 1
}

# --- sanity check: template root looks right ---
if (-not (Test-Path (Join-Path $TemplateRoot 'pixi.toml'))) {
    Write-Host "error: $TemplateRoot does not look like a template root (no pixi.toml)" -ForegroundColor Red
    exit 2
}

# --- list of files we operate on ---
$IncludedPatterns = @(
    '*.toml', '*.py', '*.md', '*.sbatch', '*.sh', '*.ps1',
    '*.yml', '*.yaml', 'Dockerfile*', '*.def',
    '.env.example', '.env.template'
)
$ExcludedDirSegments = @('\.git\', '\.pixi\', '\node_modules\', '__pycache__')

function Get-TargetFiles {
    Get-ChildItem -Path $TemplateRoot -Recurse -File -Include $IncludedPatterns -ErrorAction SilentlyContinue |
        Where-Object {
            $p = $_.FullName
            -not ($ExcludedDirSegments | Where-Object { $p -like "*$_*" })
        }
}

# --- idempotency: if no tokens remain anywhere, exit 0 ---
$TokenPattern = '__PACKAGE_NAME__|__PROJECT_SLUG__|__PROJECT_DESCRIPTION__'
$TokenHits = Get-TargetFiles | Select-String -Pattern $TokenPattern -List -ErrorAction SilentlyContinue

$SrcTokenDir = Join-Path $TemplateRoot 'src\__PACKAGE_NAME__'

if (-not $TokenHits -and -not (Test-Path $SrcTokenDir)) {
    Write-Host 'Template already instantiated; nothing to do.'
    exit 0
}

if (-not $TokenHits) {
    Write-Host 'Template already instantiated; nothing to do.'
    exit 0
}

if (-not (Test-Path $SrcTokenDir)) {
    Die "src\__PACKAGE_NAME__\ missing — cannot instantiate"
}

# --- validators ---
function Test-PackageName([string]$n) { return $n -match '^[a-z][a-z0-9_]*$' }
function Test-Slug        ([string]$n) { return $n -match '^[a-z][a-z0-9-]*$' }

$Interactive = -not ($PackageName -or $Slug -or $Description)

if ($Interactive) {
    Write-Host 'Instantiating v3se-templates.'
    Write-Host ''

    while (-not $PackageName) {
        $PackageName = Read-Host 'Python package name (snake_case, e.g. crash_survey)'
        if ($PackageName -and -not (Test-PackageName $PackageName)) {
            Write-Host '  -> must match ^[a-z][a-z0-9_]*$'
            $PackageName = $null
        }
    }

    $DefaultSlug = $PackageName -replace '_', '-'
    while (-not $Slug) {
        $Slug = Read-Host "Project slug (kebab-case, default: $DefaultSlug)"
        if (-not $Slug) { $Slug = $DefaultSlug }
        if (-not (Test-Slug $Slug)) {
            Write-Host '  -> must match ^[a-z][a-z0-9-]*$'
            $Slug = $null
        }
    }

    while (-not $Description) {
        $Description = Read-Host 'One-line project description'
    }

    Write-Host ''
    Write-Host 'Summary:'
    Write-Host "  package name : $PackageName"
    Write-Host "  project slug : $Slug"
    Write-Host "  description  : $Description"
    Write-Host ''
    $confirm = Read-Host 'Proceed? [y/N]'
    if ($confirm -notin @('y','Y','yes','YES')) {
        Write-Host 'aborted.'
        exit 1
    }
}

# --- validate (covers both interactive and parameterised paths) ---
if (-not $PackageName) { Die 'missing -PackageName' }
if (-not $Slug)        { Die 'missing -Slug' }
if (-not $Description) { Die 'missing -Description' }
if (-not (Test-PackageName $PackageName)) {
    Die "package name '$PackageName' must be snake_case (^[a-z][a-z0-9_]*`$)"
}
if (-not (Test-Slug $Slug)) {
    Die "slug '$Slug' must be kebab-case (^[a-z][a-z0-9-]*`$)"
}

# --- substitution ---
Write-Host ''
Write-Host 'Substituting tokens across the tree...'

$Replacements = [ordered]@{
    '__PACKAGE_NAME__'        = $PackageName
    '__PROJECT_SLUG__'        = $Slug
    '__PROJECT_DESCRIPTION__' = $Description
}

foreach ($file in Get-TargetFiles) {
    $content = Get-Content -Raw -LiteralPath $file.FullName -ErrorAction SilentlyContinue
    if ($null -eq $content) { continue }
    if ($content -notmatch $TokenPattern) { continue }

    $new = $content
    foreach ($k in $Replacements.Keys) {
        $new = $new.Replace($k, $Replacements[$k])
    }

    if ($new -ne $content) {
        # Preserve original encoding: write as UTF-8 without BOM.
        $enc = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($file.FullName, $new, $enc)
        $rel = $file.FullName.Substring($TemplateRoot.Length).TrimStart('\','/')
        Write-Host "  rewrote: $rel"
    }
}

# --- rename src/__PACKAGE_NAME__/ ---
if (Test-Path $SrcTokenDir) {
    $newSrcDir = Join-Path $TemplateRoot "src\$PackageName"
    Rename-Item -LiteralPath $SrcTokenDir -NewName $PackageName
    Write-Host "  renamed: src\__PACKAGE_NAME__\ -> src\$PackageName\"
}

# --- self-delete ---
$selfSh  = Join-Path $TemplateRoot 'scripts\instantiate.sh'
$selfPs1 = Join-Path $TemplateRoot 'scripts\instantiate.ps1'
if (Test-Path $selfSh)  { Remove-Item -LiteralPath $selfSh  -Force }
if (Test-Path $selfPs1) { Remove-Item -LiteralPath $selfPs1 -Force }
Write-Host '  removed: scripts\instantiate.sh, scripts\instantiate.ps1'

Write-Host ''
Write-Host 'Instantiated.'
Write-Host 'Next:'
Write-Host '  1. Copy-Item .env.example .env   (fill in CEPHYR_USER, Slurm account, ...)'
Write-Host '  2. docker compose up -d dev'
Write-Host '  3. docker compose exec dev pixi install'
Write-Host '  4. docker compose exec dev pixi run smoke'
