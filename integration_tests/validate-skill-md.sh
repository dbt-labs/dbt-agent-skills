#!/usr/bin/env bash

# Copyright 2026 yu-iskw
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Validate SKILL.md frontmatter against rules in CLAUDE.md
set -euo pipefail

# Default plugin directory
PLUGIN_DIR="${1:-.}"

echo "Validating SKILL.md files in ${PLUGIN_DIR}..."

# Find all SKILL.md files in the plugin directory
# Exclude node_modules if any
SKILL_FILES=$(find "${PLUGIN_DIR}" -name "SKILL.md" -type f -not -path "*/node_modules/*")

if [[ -z "${SKILL_FILES}" ]]; then
	echo "No SKILL.md files found in ${PLUGIN_DIR}."
	exit 0
fi

errors=0

for skill_file in ${SKILL_FILES}; do
	# Use node or python3 to parse frontmatter and validate
	if command -v node >/dev/null 2>&1; then
		if ! node - "${skill_file}" <<'EOF'
const fs = require("fs");
const path = require("path");
const skillFile = process.argv[2];

// Get the directory name of the skill
const skillDir = path.basename(path.dirname(skillFile));

let content;
try {
  content = fs.readFileSync(skillFile, "utf8");
} catch (e) {
  console.error(`ERROR: Could not read ${skillFile}`);
  process.exit(1);
}

// Extract frontmatter
const fmMatch = content.match(/^---\r?\n([\s\S]*?)\n---/);
if (!fmMatch) {
  console.error(`ERROR: No valid frontmatter (--- ... ---) found in ${skillFile}`);
  process.exit(1);
}

const fmText = fmMatch[1];
const fm = {};
const lines = fmText.split(/\r?\n/);

// Simple YAML parser for top-level keys
let currentKey = null;
for (const line of lines) {
  const topLevelMatch = line.match(/^([a-z0-9-]+):\s*(.*)$/i);
  if (topLevelMatch) {
    currentKey = topLevelMatch[1];
    let val = topLevelMatch[2].trim();
    if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
    if (val.startsWith("'") && val.endsWith("'")) val = val.slice(1, -1);
    fm[currentKey] = val;
  }
}

const requiredFields = ["name", "description"];
const allowedFields = ["name", "description", "allowed-tools", "compatibility", "license", "metadata", "user-invocable"];
const forbiddenFields = ["version", "author", "tags"];

// 1. Check required fields
for (const field of requiredFields) {
  if (!fm[field]) {
    console.error(`ERROR: Missing required field '${field}' in ${skillFile}`);
    process.exit(1);
  }
}

// 2. Check for unexpected or forbidden top-level fields
for (const key of Object.keys(fm)) {
  if (!allowedFields.includes(key)) {
    console.error(`ERROR: Unexpected field '${key}' in frontmatter of ${skillFile}. Only allowed: ${allowedFields.join(", ")}`);
    process.exit(1);
  }
  if (forbiddenFields.includes(key)) {
    console.error(`ERROR: Field '${key}' must be inside 'metadata:' in ${skillFile} per CLAUDE.md`);
    process.exit(1);
  }
}

// 3. Validate name matches directory name exactly
if (fm.name !== skillDir) {
  console.error(`ERROR: Skill name '${fm.name}' does not match directory name '${skillDir}' for ${skillFile}`);
  process.exit(1);
}

// 4. Validate name format (lowercase with hyphens only)
if (!/^[a-z0-9-]+$/.test(fm.name)) {
  console.error(`ERROR: Skill name '${fm.name}' must be lowercase with hyphens only in ${skillFile}`);
  process.exit(1);
}

console.log(`OK: ${skillFile} (name: ${fm.name})`);
EOF
		then
			errors=$((errors + 1))
		fi
	elif command -v python3 >/dev/null 2>&1; then
		if ! python3 - "${skill_file}" <<'EOF'
import sys
import os
import re

skill_file = sys.argv[1]
skill_dir = os.path.basename(os.path.dirname(skill_file))

try:
    with open(skill_file, 'r', encoding='utf-8') as f:
        content = f.read()
except Exception as e:
    print(f"ERROR: Could not read {skill_file}: {e}")
    sys.exit(1)

fm_match = re.match(r'^---\r?\n(.*?)\n---', content, re.DOTALL)
if not fm_match:
    print(f"ERROR: No valid frontmatter (--- ... ---) found in {skill_file}")
    sys.exit(1)

fm_text = fm_match.group(1)
fm = {}
lines = fm_text.splitlines()

for line in lines:
    match = re.match(r'^([a-z0-9-]+):\s*(.*)$', line, re.IGNORECASE)
    if match:
        key = match.group(1)
        val = match.group(2).strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        fm[key] = val

required_fields = ["name", "description"]
allowed_fields = ["name", "description", "allowed-tools", "compatibility", "license", "metadata", "user-invocable"]
forbidden_fields = ["version", "author", "tags"]

for field in required_fields:
    if field not in fm:
        print(f"ERROR: Missing required field '{field}' in {skill_file}")
        sys.exit(1)

for key in fm:
    if key not in allowed_fields:
        print(f"ERROR: Unexpected field '{key}' in frontmatter of {skill_file}. Only allowed: {', '.join(allowed_fields)}")
        sys.exit(1)
    if key in forbidden_fields:
        print(f"ERROR: Field '{key}' must be inside 'metadata:' in {skill_file} per CLAUDE.md")
        sys.exit(1)

if fm['name'] != skill_dir:
    print(f"ERROR: Skill name '{fm['name']}' does not match directory name '{skill_dir}' for {skill_file}")
    sys.exit(1)

if not re.match(r'^[a-z0-9-]+$', fm['name']):
    print(f"ERROR: Skill name '{fm['name']}' must be lowercase with hyphens only in {skill_file}")
    sys.exit(1)

print(f"OK: {skill_file} (name: {fm['name']})")
EOF
		then
			errors=$((errors + 1))
		fi
	else
		echo "ERROR: Neither node nor python3 is available for skill validation"
		exit 1
	fi
done

if [[ ${errors} -gt 0 ]]; then
	echo "Skill validation found ${errors} error(s) in ${PLUGIN_DIR}"
	exit 1
fi

echo "Skill validation passed for ${PLUGIN_DIR}"
exit 0
