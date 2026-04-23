#!/usr/bin/env bash
# =============================================================================
# instantiate.sh — one-shot bootstrap for the v3se-templates scaffold.
#
# Substitutes three placeholder tokens across the tree:
#   __PACKAGE_NAME__         Python identifier (snake_case)
#   __PROJECT_SLUG__         display / workspace name (kebab-case)
#   __PROJECT_DESCRIPTION__  free-form one-liner
#
# Usage:
#   bash scripts/instantiate.sh
#     (interactive — prompts for all three values)
#
#   bash scripts/instantiate.sh \
#       --package-name crash_survey \
#       --slug crash-survey \
#       --description "Survey of crashes"
#     (non-interactive — one shot)
#
# Exit codes:
#   0  success (or already instantiated; nothing to do)
#   1  bad invocation / validation error
#   2  not run from template root
# =============================================================================

set -euo pipefail

# --- locate template root (repo root, where pixi.toml + src/__PACKAGE_NAME__/ live) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

die() { echo "error: $*" >&2; exit 1; }

# --- arg parsing ---
PACKAGE_NAME=""
PROJECT_SLUG=""
PROJECT_DESCRIPTION=""
INTERACTIVE=1

while [ $# -gt 0 ]; do
    case "$1" in
        --package-name)
            PACKAGE_NAME="${2:-}"; shift 2; INTERACTIVE=0 ;;
        --slug)
            PROJECT_SLUG="${2:-}"; shift 2; INTERACTIVE=0 ;;
        --description)
            PROJECT_DESCRIPTION="${2:-}"; shift 2; INTERACTIVE=0 ;;
        -h|--help)
            sed -n '2,25p' "$0"; exit 0 ;;
        *)
            die "unknown argument: $1" ;;
    esac
done

# --- sanity: are we actually in a template root? ---
[ -f "$TEMPLATE_ROOT/pixi.toml" ] \
    || { echo "error: $TEMPLATE_ROOT does not look like a template root (no pixi.toml)" >&2; exit 2; }

# --- idempotency: if no tokens remain anywhere, exit 0 ---
# grep returns 1 when nothing matches, 0 when there are matches.
TOKEN_HITS=0
for tok in __PACKAGE_NAME__ __PROJECT_SLUG__ __PROJECT_DESCRIPTION__; do
    if grep -rlI --exclude-dir=.git --exclude-dir=.pixi --exclude-dir=node_modules \
            -- "$tok" "$TEMPLATE_ROOT" >/dev/null 2>&1; then
        TOKEN_HITS=1
        break
    fi
done

# Also check whether the token directory still exists.
if [ ! -d "$TEMPLATE_ROOT/src/__PACKAGE_NAME__" ]; then
    # directory has been renamed already; combined with no token hits, treat as already instantiated
    if [ "$TOKEN_HITS" -eq 0 ]; then
        echo "Template already instantiated; nothing to do."
        exit 0
    fi
fi

if [ "$TOKEN_HITS" -eq 0 ]; then
    echo "Template already instantiated; nothing to do."
    exit 0
fi

[ -d "$TEMPLATE_ROOT/src/__PACKAGE_NAME__" ] \
    || { echo "error: src/__PACKAGE_NAME__/ missing — cannot instantiate" >&2; exit 2; }

# --- validators ---
validate_package_name() {
    if ! [[ "$1" =~ ^[a-z][a-z0-9_]*$ ]]; then
        die "package name '$1' must be snake_case (^[a-z][a-z0-9_]*\$)"
    fi
}
validate_slug() {
    if ! [[ "$1" =~ ^[a-z][a-z0-9-]*$ ]]; then
        die "slug '$1' must be kebab-case (^[a-z][a-z0-9-]*\$)"
    fi
}

# --- interactive prompting ---
if [ "$INTERACTIVE" -eq 1 ]; then
    echo "Instantiating v3se-templates."
    echo

    while [ -z "$PACKAGE_NAME" ]; do
        read -r -p "Python package name (snake_case, e.g. crash_survey): " PACKAGE_NAME
        if [ -n "$PACKAGE_NAME" ] && ! [[ "$PACKAGE_NAME" =~ ^[a-z][a-z0-9_]*$ ]]; then
            echo "  -> must match ^[a-z][a-z0-9_]*\$"
            PACKAGE_NAME=""
        fi
    done

    DEFAULT_SLUG="${PACKAGE_NAME//_/-}"
    while [ -z "$PROJECT_SLUG" ]; do
        read -r -p "Project slug (kebab-case, default: $DEFAULT_SLUG): " PROJECT_SLUG
        PROJECT_SLUG="${PROJECT_SLUG:-$DEFAULT_SLUG}"
        if ! [[ "$PROJECT_SLUG" =~ ^[a-z][a-z0-9-]*$ ]]; then
            echo "  -> must match ^[a-z][a-z0-9-]*\$"
            PROJECT_SLUG=""
        fi
    done

    while [ -z "$PROJECT_DESCRIPTION" ]; do
        read -r -p "One-line project description: " PROJECT_DESCRIPTION
    done

    echo
    echo "Summary:"
    echo "  package name : $PACKAGE_NAME"
    echo "  project slug : $PROJECT_SLUG"
    echo "  description  : $PROJECT_DESCRIPTION"
    echo
    read -r -p "Proceed? [y/N] " confirm
    case "$confirm" in
        y|Y|yes|YES) ;;
        *) echo "aborted."; exit 1 ;;
    esac
fi

# --- non-interactive validation ---
[ -n "$PACKAGE_NAME" ]         || die "missing --package-name"
[ -n "$PROJECT_SLUG" ]         || die "missing --slug"
[ -n "$PROJECT_DESCRIPTION" ]  || die "missing --description"

validate_package_name "$PACKAGE_NAME"
validate_slug         "$PROJECT_SLUG"

# --- substitution ---
# Use a portable sed replace that escapes slashes and ampersands in the replacement text
# (descriptions may contain arbitrary characters).
sed_escape() {
    # Escapes characters that are special on the replacement side of sed's s///
    printf '%s' "$1" | sed -e 's/[\\/&|]/\\&/g'
}

ESC_PACKAGE_NAME="$(sed_escape "$PACKAGE_NAME")"
ESC_PROJECT_SLUG="$(sed_escape "$PROJECT_SLUG")"
ESC_PROJECT_DESCRIPTION="$(sed_escape "$PROJECT_DESCRIPTION")"

echo
echo "Substituting tokens across the tree..."

# Gather every target file. Use -print0 / read -r -d '' for path safety.
# Expressed as a single find so we avoid spawning one per extension.
while IFS= read -r -d '' f; do
    # Skip binary-ish / irrelevant
    case "$f" in
        */.git/*|*/.pixi/*|*/node_modules/*|*/__pycache__/*) continue ;;
    esac
    # Only rewrite if one of the tokens is actually present — avoids touching mtimes needlessly.
    if grep -qI -e '__PACKAGE_NAME__' -e '__PROJECT_SLUG__' -e '__PROJECT_DESCRIPTION__' "$f" 2>/dev/null; then
        # Portable sed -i (BSD and GNU disagree on -i semantics)
        tmp="$(mktemp)"
        sed \
            -e "s|__PACKAGE_NAME__|$ESC_PACKAGE_NAME|g" \
            -e "s|__PROJECT_SLUG__|$ESC_PROJECT_SLUG|g" \
            -e "s|__PROJECT_DESCRIPTION__|$ESC_PROJECT_DESCRIPTION|g" \
            "$f" > "$tmp"
        # Preserve exec bit
        if [ -x "$f" ]; then chmod +x "$tmp"; fi
        mv "$tmp" "$f"
        echo "  rewrote: ${f#$TEMPLATE_ROOT/}"
    fi
done < <(find "$TEMPLATE_ROOT" \
    \( -name '*.toml' -o -name '*.py' -o -name '*.md' \
       -o -name '*.sbatch' -o -name '*.sh' -o -name '*.ps1' \
       -o -name '*.yml' -o -name '*.yaml' \
       -o -name 'Dockerfile*' -o -name '*.def' \
       -o -name '.env.example' -o -name '.env.template' \) \
    -not -path '*/.git/*' -not -path '*/.pixi/*' \
    -not -path '*/node_modules/*' -not -path '*/__pycache__/*' \
    -print0)

# --- rename src/__PACKAGE_NAME__/ ---
if [ -d "$TEMPLATE_ROOT/src/__PACKAGE_NAME__" ]; then
    mv "$TEMPLATE_ROOT/src/__PACKAGE_NAME__" "$TEMPLATE_ROOT/src/$PACKAGE_NAME"
    echo "  renamed: src/__PACKAGE_NAME__/ -> src/$PACKAGE_NAME/"
fi

# --- self-delete ---
rm -f "$TEMPLATE_ROOT/scripts/instantiate.sh" "$TEMPLATE_ROOT/scripts/instantiate.ps1"
echo "  removed: scripts/instantiate.sh, scripts/instantiate.ps1"

echo
echo "Instantiated."
echo "Next:"
echo "  1. cp .env.example .env   (fill in CEPHYR_USER, Slurm account, ...)"
echo "  2. docker compose up -d dev"
echo "  3. docker compose exec dev pixi install"
echo "  4. docker compose exec dev pixi run smoke"
