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

# Test plugin loading and discovery with Claude CLI
set -euo pipefail

# Check if Claude CLI is available
if ! command -v claude >/dev/null 2>&1; then
	echo "WARNING: Claude CLI not found. Skipping plugin loading tests."
	echo "Install with: npm install -g @anthropic-ai/claude-code"
	exit 0
fi

# Default plugin directory
PLUGIN_DIR="${1:-.}"
MANIFEST_PATH="${PLUGIN_DIR}/.claude-plugin/plugin.json"

# Get plugin name from manifest
if command -v jq >/dev/null 2>&1; then
	plugin_name="$(jq -r '.name' "${MANIFEST_PATH}")"
elif command -v node >/dev/null 2>&1; then
	plugin_name="$(node -p "require('${MANIFEST_PATH}').name")"
else
	echo "ERROR: Cannot read manifest. Neither jq nor node is available."
	exit 1
fi

echo "Testing plugin loading for: ${plugin_name}"

# Test 1: Plugin loads without errors
echo "Testing plugin loading with --plugin-dir..."
if ! claude --plugin-dir "${PLUGIN_DIR}" --help >/dev/null 2>&1; then
	echo "ERROR: Plugin failed to load with 'claude --plugin-dir ${PLUGIN_DIR} --help'"
	claude --plugin-dir "${PLUGIN_DIR}" --help || true
	exit 1
fi
echo "Plugin loaded successfully"

# Test 2: Plugin manifest validates via Claude CLI
echo "Testing plugin manifest validation via Claude CLI..."
if ! claude plugin validate "${PLUGIN_DIR}" >/dev/null 2>&1; then
	echo "ERROR: Plugin validation failed with 'claude plugin validate ${PLUGIN_DIR}'"
	claude plugin validate "${PLUGIN_DIR}" || true
	exit 1
fi
echo "Plugin validation test passed"
