#!/usr/bin/env bash
set -euo pipefail

# AgentSpec Codex plugin installer
# Usage:
#   bash install.sh                    # install the release-pinned plugin + register
#   bash install.sh --ref main         # install the development plugin from main
#   bash install.sh --codex-plugin     # same as above
#   bash install.sh --local            # use this checkout as the plugin source

REPO_URL="https://github.com/yimwoo/agent-spec"
DEFAULT_SOURCE_REF="v0.1.40"
SOURCE_REF="${AGENTSPEC_REF:-${DEFAULT_SOURCE_REF}}"
SOURCE_DIR="$HOME/.codex/plugins/agentspec-source"
PLUGIN_SUBDIR="agentspec-codex-plugin"
MARKETPLACE_FILE="$HOME/.agents/plugins/marketplace.json"
CODEX_PLUGIN_CACHE_ROOT="$HOME/.codex/plugins/cache/codex-plugins/aspec"

ensure_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Error: ${command_name} is required." >&2
    exit 1
  fi
}

ensure_clean_checkout() {
  local source_dir="$1"

  if [ -n "$(git -C "${source_dir}" status --porcelain)" ]; then
    echo "Error: ${source_dir} has local changes." >&2
    echo "Commit or stash them first, or use --local from the repo you want Codex to load." >&2
    exit 1
  fi
}

checkout_source_ref() {
  local source_dir="$1"
  local source_ref="$2"

  ensure_clean_checkout "${source_dir}"
  git -C "${source_dir}" fetch --tags origin
  if [ "${source_ref}" = "main" ]; then
    git -C "${source_dir}" checkout main
    git -C "${source_dir}" pull --ff-only origin main
    return 0
  fi

  if ! git -C "${source_dir}" rev-parse --verify "${source_ref}^{commit}" >/dev/null 2>&1; then
    echo "Error: AgentSpec source ref not found: ${source_ref}" >&2
    echo "Use a release tag such as ${DEFAULT_SOURCE_REF}, or pass --ref main for development." >&2
    exit 1
  fi
  git -C "${source_dir}" checkout --detach "${source_ref}"
}

verify_cli_plugin_compatibility() {
  local manifest_path="$1"
  local plugin_version
  local cli_version

  plugin_version="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "${manifest_path}")"
  cli_version="$(python3 -c '
import importlib.metadata

try:
    print(importlib.metadata.version("agentspec"))
except importlib.metadata.PackageNotFoundError:
    print("")
')"

  if [ -z "${cli_version}" ]; then
    echo "AgentSpec CLI is not installed yet; install v${plugin_version} before governed execution."
    return 0
  fi
  if [ "${cli_version}" = "${plugin_version}" ]; then
    echo "AgentSpec CLI/plugin compatibility verified: ${plugin_version}."
    return 0
  fi
  if [ "${ALLOW_VERSION_MISMATCH}" = true ]; then
    echo "Warning: AgentSpec CLI ${cli_version} does not match plugin ${plugin_version}." >&2
    return 0
  fi

  echo "Error: AgentSpec CLI ${cli_version} does not match plugin ${plugin_version}." >&2
  echo "Install the matching CLI or rerun with --allow-version-mismatch for intentional development testing." >&2
  exit 1
}

refresh_codex_plugin_cache() {
  local plugin_path="$1"
  local cache_root="${CODEX_PLUGIN_CACHE_ROOT}"
  local refreshed=0

  if [ ! -d "${plugin_path}" ]; then
    return 0
  fi

  if ! command -v rsync >/dev/null 2>&1; then
    return 0
  fi

  if [ -d "${cache_root}" ]; then
    for cache_dir in "${cache_root}"/*/; do
      [ -d "${cache_dir}" ] || continue
      echo "Refreshing Codex plugin cache at ${cache_dir}..."
      mkdir -p "${cache_dir}"
      rsync -a --delete --exclude '.git' "${plugin_path}/" "${cache_dir}"
      refreshed=1
    done
  fi

  if [ "${refreshed}" -eq 0 ]; then
    local seed_dir="${cache_root}/local"
    echo "Seeding Codex plugin cache at ${seed_dir}..."
    mkdir -p "${seed_dir}"
    rsync -a --delete --exclude '.git' "${plugin_path}/" "${seed_dir}/"
    refreshed=1
  fi

  if [ "${refreshed}" -eq 1 ]; then
    echo "  Codex plugin cache refreshed."
  fi
}

register_marketplace() {
  local manifest_path="$1"
  local dest_path="$2"
  local plugin_source_path="$3"

  python3 -c '
import json, os, sys

manifest_path = sys.argv[1]
dest_path = sys.argv[2]
plugin_source_path = sys.argv[3]
owner_name = os.environ.get("USER", "unknown")
marketplace_root = os.path.abspath(os.path.join(os.path.dirname(dest_path), "..", ".."))
plugin_source_abs = os.path.abspath(plugin_source_path)

with open(manifest_path, encoding="utf-8") as f:
    manifest = json.load(f)

relative_plugin_path = os.path.relpath(plugin_source_abs, marketplace_root)
if relative_plugin_path == ".":
    marketplace_path = "./"
elif relative_plugin_path.startswith(".."):
    raise SystemExit(
        "Error: plugin source must live inside the marketplace root: " + marketplace_root
    )
else:
    marketplace_path = "./" + relative_plugin_path.replace(os.sep, "/")

entry = {
    "name": manifest["name"],
    "description": manifest["description"],
    "version": manifest["version"],
    "author": manifest.get("author", {"name": owner_name}),
    "source": {
        "source": "local",
        "path": marketplace_path,
    },
    "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    },
    "category": manifest.get("interface", {}).get("category", "Developer Tools"),
}

if "interface" in manifest:
    entry["interface"] = manifest["interface"]

if os.path.exists(dest_path):
    with open(dest_path, encoding="utf-8") as f:
        dest = json.load(f)
else:
    dest = {
        "name": "codex-plugins",
        "description": "Codex plugin marketplace",
        "owner": {"name": owner_name},
        "interface": {"displayName": "Local Plugins"},
        "plugins": [],
    }

dest.setdefault("name", "codex-plugins")
dest.setdefault("description", "Codex plugin marketplace")
dest.setdefault("owner", {"name": owner_name})
dest.setdefault("interface", {"displayName": "Local Plugins"})
dest.setdefault("plugins", [])

existing_index = None
for i, plugin in enumerate(dest["plugins"]):
    if plugin and plugin.get("name") == manifest["name"]:
        existing_index = i
        break

if existing_index is not None:
    dest["plugins"][existing_index] = entry
    action = "Updated"
else:
    dest["plugins"].append(entry)
    action = "Added"

with open(dest_path, "w", encoding="utf-8") as f:
    json.dump(dest, f, indent=2)
    f.write("\n")

print(action + " AgentSpec plugin entry (version " + entry["version"] + ")")
' "$manifest_path" "$dest_path" "$plugin_source_path"
}

LOCAL_MODE=false
ALLOW_VERSION_MISMATCH=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --local)
      LOCAL_MODE=true
      shift
      ;;
    --codex-plugin)
      shift
      ;;
    --ref)
      if [ "$#" -lt 2 ]; then
        echo "Error: --ref requires a release tag or main." >&2
        exit 1
      fi
      SOURCE_REF="$2"
      shift 2
      ;;
    --allow-version-mismatch)
      ALLOW_VERSION_MISMATCH=true
      shift
      ;;
    --help|-h)
      echo "AgentSpec Codex Plugin Installer"
      echo ""
      echo "Usage:"
      echo "  bash install.sh                  Install ${DEFAULT_SOURCE_REF} (stable default)"
      echo "  bash install.sh --ref main       Install the development plugin from main"
      echo "  bash install.sh --local          Use current checkout as plugin source"
      echo "  bash install.sh --allow-version-mismatch"
      echo "                                   Permit intentional CLI/plugin skew"
      echo ""
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ensure_command git
ensure_command python3

if [ "${LOCAL_MODE}" = true ]; then
  SOURCE_REF="local"
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PLUGIN_PATH="${REPO_ROOT}/${PLUGIN_SUBDIR}"
  MARKETPLACE_FILE="${REPO_ROOT}/.agents/plugins/marketplace.json"
  echo "Local mode: using ${PLUGIN_PATH} as plugin source"
else
  if [ -d "${SOURCE_DIR}/.git" ]; then
    echo "Updating existing source checkout at ${SOURCE_DIR}..."
    checkout_source_ref "${SOURCE_DIR}" "${SOURCE_REF}"
  else
    echo "Cloning AgentSpec to ${SOURCE_DIR}..."
    mkdir -p "$(dirname "${SOURCE_DIR}")"
    git clone "${REPO_URL}" "${SOURCE_DIR}"
    checkout_source_ref "${SOURCE_DIR}" "${SOURCE_REF}"
  fi
  PLUGIN_PATH="${SOURCE_DIR}/${PLUGIN_SUBDIR}"
fi

PLUGIN_MANIFEST="${PLUGIN_PATH}/.codex-plugin/plugin.json"
if [ ! -f "${PLUGIN_MANIFEST}" ]; then
  echo "Error: ${PLUGIN_MANIFEST} not found." >&2
  exit 1
fi

verify_cli_plugin_compatibility "${PLUGIN_MANIFEST}"

MARKETPLACE_DIR="$(dirname "${MARKETPLACE_FILE}")"
mkdir -p "${MARKETPLACE_DIR}"

register_marketplace "${PLUGIN_MANIFEST}" "${MARKETPLACE_FILE}" "${PLUGIN_PATH}"
refresh_codex_plugin_cache "${PLUGIN_PATH}"

echo ""
echo "AgentSpec Codex plugin installed successfully."
echo ""
echo "Next steps:"
echo "  1. Install the AgentSpec CLI if needed:"
echo ""
PLUGIN_VERSION="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "${PLUGIN_MANIFEST}")"
echo "     python3 -m pip install \"git+https://github.com/yimwoo/agent-spec.git@v${PLUGIN_VERSION}\""
echo ""
echo "  2. Codex CLI: run 'codex', then '/plugins', choose the local marketplace,"
echo "     open aspec, and select Install plugin or toggle it on."
echo ""
echo "  3. Codex app: restart Codex, open Plugins > Local Plugins, and install aspec."
echo ""
echo "  4. Open your target repo:"
echo ""
echo "     cd <your-project>"
echo "     codex"
echo ""
echo "  5. Ask Codex:"
echo ""
echo "     Use aspec:init-project to initialize this repository from docs/source/design.md."
echo ""
echo "Plugin source: ${PLUGIN_PATH}"
echo "Source ref:    ${SOURCE_REF}"
echo "Marketplace:   ${MARKETPLACE_FILE}"
