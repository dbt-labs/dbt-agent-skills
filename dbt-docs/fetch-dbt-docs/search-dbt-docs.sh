#!/usr/bin/env bash
#
# search-dbt-docs.sh - Search dbt full docs for keywords and return matching page URLs
#
# Usage: ./search-dbt-docs.sh <keyword> [keyword2] [keyword3] ...
#
# Works on macOS, Linux, Git Bash (Windows), and WSL

set -euo pipefail

FULL_URL="https://docs.getdbt.com/llms-full.txt"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/dbt-docs"
CACHE_FILE="$CACHE_DIR/llms-full.txt"
CACHE_MAX_AGE=86400  # 24 hours in seconds

# Colors (disabled if not a terminal)
if [[ -t 1 ]]; then
    BOLD='\033[1m'
    DIM='\033[2m'
    RESET='\033[0m'
else
    BOLD=''
    DIM=''
    RESET=''
fi

usage() {
    echo "Usage: $0 <keyword> [keyword2] [keyword3] ..."
    echo ""
    echo "Search dbt documentation for keywords and return matching page URLs."
    echo ""
    echo "Options:"
    echo "  -f, --fresh     Force fresh download (ignore cache)"
    echo "  -h, --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 semantic_model"
    echo "  $0 metric dimension"
    echo "  $0 'incremental strategy'"
    exit 1
}

# Parse arguments
FRESH=false
KEYWORDS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--fresh)
            FRESH=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            ;;
        *)
            KEYWORDS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#KEYWORDS[@]} -eq 0 ]]; then
    echo "Error: At least one keyword required"
    usage
fi

# Ensure cache directory exists
mkdir -p "$CACHE_DIR"

# Check if file needs download
need_download() {
    if [[ "$FRESH" == "true" ]]; then
        return 0
    fi
    if [[ ! -f "$CACHE_FILE" ]]; then
        return 0
    fi
    # Check file age (cross-platform)
    local file_age
    if [[ "$(uname)" == "Darwin" ]]; then
        file_age=$(( $(date +%s) - $(stat -f %m "$CACHE_FILE") ))
    else
        file_age=$(( $(date +%s) - $(stat -c %Y "$CACHE_FILE") ))
    fi
    [[ $file_age -gt $CACHE_MAX_AGE ]]
}

# Download if needed
if need_download; then
    echo -e "${DIM}Downloading dbt docs...${RESET}" >&2
    curl -sL "$FULL_URL" -o "$CACHE_FILE"
    echo -e "${DIM}Cached at: $CACHE_FILE${RESET}" >&2
fi

# Convert keywords to lowercase for matching
keywords_lower=""
for kw in "${KEYWORDS[@]}"; do
    keywords_lower="$keywords_lower|$(echo "$kw" | tr '[:upper:]' '[:lower:]')"
done
keywords_lower="${keywords_lower:1}"  # Remove leading |

echo -e "${BOLD}Searching for: ${KEYWORDS[*]}${RESET}" >&2
echo "" >&2

# Search: find pages containing keywords
# Logic:
# 1. Page delimiter is: --- followed by ###
# 2. After delimiter, first docs.getdbt.com link is the page URL
# 3. Match keywords in content, output unique page URLs
results=$(awk -v keywords="$keywords_lower" '
BEGIN {
    current_url = ""
    page_count = 0
    in_new_page = 0
    n = split(keywords, kw_arr, "|")
}

# Detect page delimiter
/^---$/ {
    in_new_page = 1
    next
}

# After ---, look for ### header to confirm new page
in_new_page && /^### / {
    in_new_page = 2  # Now looking for first docs.getdbt.com link
    next
}

# Find first docs.getdbt.com URL after page header
in_new_page == 2 && /docs\.getdbt\.com/ {
    # Extract URL from markdown link: [text](URL) or just URL
    line = $0
    # Try to find (https://docs.getdbt.com/...)
    if (match(line, /\(https:\/\/docs\.getdbt\.com\/[^)]+\)/)) {
        url = substr(line, RSTART+1, RLENGTH-2)
        current_url = url
        in_new_page = 0
    } else if (match(line, /https:\/\/docs\.getdbt\.com\/[^ \t\n\])]+/)) {
        current_url = substr(line, RSTART, RLENGTH)
        in_new_page = 0
    }
}

# Reset if we hit another --- without finding URL
in_new_page && /^---$/ {
    in_new_page = 1
}

# Check content for keyword matches
{
    if (current_url == "") next

    line_lower = tolower($0)
    for (i = 1; i <= n; i++) {
        if (index(line_lower, kw_arr[i]) > 0) {
            if (!seen[current_url]) {
                seen[current_url] = 1
                urls[++page_count] = current_url
            }
            break
        }
    }
}

END {
    for (i = 1; i <= page_count; i++) {
        print urls[i]
    }
}
' "$CACHE_FILE")

if [[ -z "$results" ]]; then
    echo "No matches found."
    exit 0
fi

echo "$results"

# Count results
count=$(echo "$results" | wc -l | tr -d ' ')
echo "" >&2
echo -e "${DIM}Found $count matching page(s)${RESET}" >&2
