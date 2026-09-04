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

# Validate plugin manifest JSON schema and required fields
set -euo pipefail

# Default plugin directory
PLUGIN_DIR="${1:-.}"
MANIFEST_PATH="${PLUGIN_DIR}/.claude-plugin/plugin.json"

# Check if manifest file exists
if [[ ! -f ${MANIFEST_PATH} ]]; then
	echo "ERROR: Manifest file not found: ${MANIFEST_PATH}"
	exit 1
fi

# Detect available JSON validator (prefer jq, fallback to node)
if command -v jq >/dev/null 2>&1; then
	# Validate JSON structure
	if ! jq -e . "${MANIFEST_PATH}" >/dev/null 2>&1; then
		echo "ERROR: Invalid JSON structure in ${MANIFEST_PATH}."
		exit 1
	fi

	# Check required fields
	for field in name version description; do
		if ! jq -e --arg field "${field}" '.[$field] | type == "string" and length > 0' "${MANIFEST_PATH}" >/dev/null 2>&1; then
			echo "ERROR: Missing required non-empty string field '${field}' in ${MANIFEST_PATH}."
			exit 1
		fi
	done

	# Validate plugin name format (kebab-case)
	plugin_name="$(jq -r '.name' "${MANIFEST_PATH}")"
	if ! jq -e '.name | test("^[a-z0-9-]+$")' "${MANIFEST_PATH}" >/dev/null 2>&1; then
		echo "ERROR: Invalid plugin name '${plugin_name}'. Name must match ^[a-z0-9-]+$ (kebab-case)."
		exit 1
	fi

	echo "Manifest validation passed for plugin: ${plugin_name}"
elif command -v node >/dev/null 2>&1; then
	# Fallback to node for JSON validation
	node - "${MANIFEST_PATH}" <<'EOF'
const fs = require("fs");
const manifestPath = process.argv[2];
let manifest;

try {
  manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
} catch (error) {
  console.error(`ERROR: Invalid JSON structure in ${manifestPath}: ${error.message}`);
  process.exit(1);
}

const requiredFields = ["name", "version", "description"];
for (const field of requiredFields) {
  if (typeof manifest[field] !== "string" || manifest[field].trim() === "") {
    console.error(`ERROR: Missing required non-empty string field '${field}' in ${manifestPath}.`);
    process.exit(1);
  }
}

if (!/^[a-z0-9-]+$/.test(manifest.name)) {
  console.error(`ERROR: Invalid plugin name '${manifest.name}' in ${manifestPath}. Expected kebab-case matching ^[a-z0-9-]+$.`);
  process.exit(1);
}

console.log(`Manifest validation passed for plugin: ${manifest.name}`);
EOF
else
	echo "ERROR: Neither jq nor node is available for JSON validation"
	exit 1
fi
