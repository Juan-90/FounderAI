# reorganize.ps1
# Executa na raiz do repositório: .\reorganize.ps1
# Reorganiza o FounderAI para a estrutura de pastas correta.

$ErrorActionPreference = "Stop"
$root = Get-Location

Write-Host "`n🔧 Iniciando reorganização do FounderAI..." -ForegroundColor Cyan

# ─────────────────────────────────────────
# 1. Cria estrutura de pastas
# ─────────────────────────────────────────

Write-Host "`n📁 Criando estrutura de pastas..." -ForegroundColor Yellow

$folders = @(
    "backend\agents",
    "backend\core",
    "backend\prompts",
    "backend\api",
    "backend\utils",
    "frontend",
    "database\schemas",
    "database\migrations",
    "memory",
    "missions",
    "tests\unit",
    "tests\integration",
    "docker",
    "scripts",
    "docs"
)

foreach ($folder in $folders) {
    $path = Join-Path $root $folder
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  ✓ $folder" -ForegroundColor Green
    } else {
        Write-Host "  · $folder (já existe)" -ForegroundColor Gray
    }
}

# ─────────────────────────────────────────
# 2. Move arquivos para os destinos corretos
# ─────────────────────────────────────────

Write-Host "`n📦 Movendo arquivos..." -ForegroundColor Yellow

# Mapeamento: origem → destino
$moves = @{
    "mission_intelligence.py" = "backend\agents\mission_intelligence.py"
    "pipeline.py"             = "backend\core\pipeline.py"
    "schemas.py"              = "backend\core\schemas.py"
    "app.py"                  = "frontend\app.py"
    "docker-compose.yml"      = "docker\docker-compose.yml"
    "Dockerfile"              = "docker\Dockerfile"
    "requirements.txt"        = "backend\requirements.txt"
}

foreach ($src in $moves.Keys) {
    $srcPath = Join-Path $root $src
    $dstPath = Join-Path $root $moves[$src]

    if (Test-Path $srcPath) {
        Move-Item -Path $srcPath -Destination $dstPath -Force
        Write-Host "  ✓ $src → $($moves[$src])" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ $src não encontrado, pulando." -ForegroundColor DarkYellow
    }
}

# ─────────────────────────────────────────
# 3. Cria __init__.py nos módulos Python
# ─────────────────────────────────────────

Write-Host "`n🐍 Criando arquivos __init__.py..." -ForegroundColor Yellow

$inits = @(
    "backend\__init__.py",
    "backend\agents\__init__.py",
    "backend\core\__init__.py",
    "backend\api\__init__.py",
    "backend\utils\__init__.py",
    "tests\__init__.py",
    "tests\unit\__init__.py",
    "tests\integration\__init__.py"
)

foreach ($init in $inits) {
    $path = Join-Path $root $init
    if (-not (Test-Path $path)) {
        New-Item -ItemType File -Path $path -Force | Out-Null
        Write-Host "  ✓ $init" -ForegroundColor Green
    } else {
        Write-Host "  · $init (já existe)" -ForegroundColor Gray
    }
}

# ─────────────────────────────────────────
# 4. Cria arquivos que faltam
# ─────────────────────────────────────────

Write-Host "`n📝 Criando arquivos base faltantes..." -ForegroundColor Yellow

# .env.example
$envExample = Join-Path $root ".env.example"
if (-not (Test-Path $envExample)) {
@"
# Fundador IA — Variáveis de Ambiente
OLLAMA_BASE_URL=http://localhost:11434
MODEL_PRIMARY=gemma4:e4b
MODEL_REASONING=qwen3:14b
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=fundador_ia
POSTGRES_USER=fundador
POSTGRES_PASSWORD=fundador
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=missions
DEBUG=false
"@ | Set-Content $envExample -Encoding UTF8
    Write-Host "  ✓ .env.example" -ForegroundColor Green
}

# pyrightconfig.json
$pyright = Join-Path $root "pyrightconfig.json"
@"
{
  "pythonVersion": "3.11",
  "pythonPlatform": "Linux",
  "include": ["backend", "frontend", "scripts"],
  "extraPaths": ["."],
  "typeCheckingMode": "basic",
  "reportMissingImports": "warning",
  "reportMissingModuleSource": "none"
}
"@ | Set-Content $pyright -Encoding UTF8
Write-Host "  ✓ pyrightconfig.json (reescrito limpo)" -ForegroundColor Green

# ─────────────────────────────────────────
# 5. Resultado final
# ─────────────────────────────────────────

Write-Host "`n✅ Reorganização concluída!" -ForegroundColor Cyan
Write-Host "`n📂 Estrutura final:" -ForegroundColor Cyan

Get-ChildItem -Recurse -Depth 3 $root |
    Where-Object { $_.FullName -notmatch "\\.git\\" -and $_.FullName -notmatch "\\.venv\\" } |
    ForEach-Object {
        $rel = $_.FullName.Replace($root.Path + "\", "")
        $indent = "  " * ($rel.Split("\").Count - 1)
        Write-Host "$indent$($_.Name)"
    }

Write-Host "`n🚀 Próximo passo: commitar a reorganização." -ForegroundColor Cyan
Write-Host '   git add -A' -ForegroundColor White
Write-Host '   git commit -m "refactor: reorganize project into proper folder structure"' -ForegroundColor White