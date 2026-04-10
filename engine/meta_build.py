import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Define any directories to skip
skipped_verse = ["astronverse-database"]

# Define the base directory for components
current_dir = Path(__file__).parent
components_dir = Path(current_dir, "components").resolve()
folders = os.listdir(components_dir)
selected_folders = folders.copy()

# Output files
# local_meta_file: aggregated meta.json from local component directories
local_meta_file = os.path.join(current_dir, "rpaexternal/meta/local_meta.json")
# merged_meta_file: merged meta list built from local component data
merged_meta_file = os.path.join(current_dir, "rpaexternal/meta/merged_meta.json")
# merged_tree_file: tree structure built from local component data
merged_tree_file = os.path.join(current_dir, "rpaexternal/meta/tree_merged.json")
# initial meta list file
initial_meta_list_file = os.path.join(current_dir, "./_resource/meta.json")


# Utility function to print colored text in the terminal
def color_log(text, color_code):
    print(f"\033[{color_code}m{text}\033[0m")


class LocalManager:
    def __init__(self, components_dir):
        self.components_dir = components_dir

    def select_folders(self, folders):
        """Prompt user to select which component folders to include in the meta build process"""
        global selected_folders
        selected = input("Enter the package number to build: ").strip()
        try:
            selected_idx = int(selected) - 1
            if 0 <= selected_idx < len(folders):
                selected_folders = [folders[selected_idx]]
            else:
                color_log("Invalid selection. Please select a valid package number.", "31")
        except Exception as e:
            color_log("Invalid input. Please select one package.", "31")
            self.select_folders(folders)

    def run_meta_scripts(self, selected_folders, skipped_verse):
        """Run meta.py in each component directory"""
        color_log("Running meta.py scripts ...", "35")
        for folder in selected_folders:
            if folder in skipped_verse:
                continue
            verse_folder = os.path.join(self.components_dir, folder)
            meta_script = os.path.join(verse_folder, "meta.py")
            if not os.path.isfile(meta_script):
                continue

            color_log(f"Running meta.py in {verse_folder}...", "36")
            try:
                subprocess.run([sys.executable, "meta.py"], cwd=verse_folder, check=True)
            except Exception as e:
                color_log(f"Failed to run meta.py in {verse_folder}: {e}", "31")

    def merge_local_meta(self, skipped_verse, local_meta_file):
        """Aggregate meta.json files from each component directory"""
        color_log("Merging local meta.json files from component directories...", "35")
        result = {}
        for folder in folders:
            if folder in skipped_verse:
                continue
            verse_folder = os.path.join(self.components_dir, folder)
            meta_json_path = os.path.join(verse_folder, "meta.json")
            if not os.path.isfile(meta_json_path):
                continue
            with open(meta_json_path, encoding="utf-8") as f:
                data = json.load(f)
                result.update(data)
        JsonUtils.save_to_file(result, local_meta_file)
        return result

    def merge_local_types(self, skipped_verse):
        """Merge meta_type.json files from component directories"""
        color_log("Merging meta_type.json files from component directories...", "35")
        result = {}
        for folder in folders:
            if folder in skipped_verse:
                continue
            verse_folder = os.path.join(self.components_dir, folder)
            types_json_path = os.path.join(verse_folder, "meta_type.json")
            if not os.path.isfile(types_json_path):
                continue
            with open(types_json_path, encoding="utf-8") as f:
                data = json.load(f)
                result.update(data)
        return result

    def build_meta_list(self, local_meta) -> list:
        """Build the merged meta list from local meta data and the initial meta list"""
        color_log("Building merged meta list from local meta data and initial meta list...", "35")
        # Placeholder for actual merging logic
        merged_meta = []
        not_local_meta = []

        for key, value in local_meta.items():
            merged_meta.append({"atomKey": key, "atomContent": json.dumps(value), "sort": None})

        with open(initial_meta_list_file, encoding="utf-8") as f:
            initial_meta_list = json.load(f)
            for item in initial_meta_list:
                if item["atomKey"] not in local_meta:
                    merged_meta.append(item)
                    not_local_meta.append(item)

        sorted_meta = sorted(merged_meta, key=lambda x: x["atomKey"])
        not_local_meta = sorted(not_local_meta, key=lambda x: x["atomKey"])
        JsonUtils.save_to_file(sorted_meta, merged_meta_file)
        JsonUtils.save_to_file(not_local_meta, os.path.join(os.path.dirname(__file__), "temp_meta_not_local.json"))
        color_log(f"Merged meta list items count: {len(sorted_meta)}", "32")
        return sorted_meta


class JsonUtils:
    """Utility class for JSON file operations and data processing"""

    @staticmethod
    def save_to_file(data, file_path):
        """Save JSON data to file"""
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def add_spaces_around_vars_in_string(text):
        """Adds spaces around @{...} variables in a string if they are missing."""
        if not isinstance(text, str):
            return text
        text = re.sub(r"(\S)(@\{.*?\})", r"\1 \2", text)
        text = re.sub(r"(@\{.*?\})(\S)", r"\1 \2", text)
        return text

    @staticmethod
    def process_data(data):
        """Recursively traverses JSON data and applies the string modification."""
        if isinstance(data, dict):
            return {k: JsonUtils.process_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [JsonUtils.process_data(item) for item in data]
        elif isinstance(data, str):
            return JsonUtils.add_spaces_around_vars_in_string(data)
        else:
            return data


class Translator:
    """Class responsible for translating text using an external translation API"""

    @staticmethod
    def translate_json(file_path, target_language="en"):
        """Translate text in a JSON file using an external translation API"""
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        # todo
        pass


class MetaBuilder:
    """Class responsible for building the merged meta and tree structures from local component data"""

    local_manager = LocalManager(components_dir)
    # Step 1: Select packages and build local meta
    color_log("=" * 60, "35")
    color_log("Step 1: Select Packages", "35")
    color_log("=" * 60, "35")

    choice = input("Select packages to build meta? (1: select one, 2: all, others: load from file): ").strip()

    if choice == "1":
        color_log("Available packages:", "35")
        for idx, folder in enumerate(folders):
            if folder in skipped_verse:
                continue
            color_log(f"  {idx + 1}. {folder}", "36")
        local_manager.select_folders(folders)
        local_manager.run_meta_scripts(selected_folders, skipped_verse)
        local_meta = local_manager.merge_local_meta(skipped_verse, local_meta_file)
        local_types = local_manager.merge_local_types(skipped_verse)
    elif choice == "2":
        selected_folders = folders.copy()
        local_manager.run_meta_scripts(selected_folders, skipped_verse)
        local_meta = local_manager.merge_local_meta(skipped_verse, local_meta_file)
        local_types = local_manager.merge_local_types(skipped_verse)
    else:
        color_log("Loading existing local meta from file...", "33")
        if not os.path.exists(local_meta_file):
            color_log(f"No local meta file found at {local_meta_file}. Please build first.", "31")
            sys.exit(1)
        with open(local_meta_file, encoding="utf-8") as f:
            local_meta = json.load(f)
        local_types = {}

    # Step 2: Build merged meta and tree
    color_log("\n" + "=" * 60, "35")
    color_log("Step 2: Build Merged Meta and Tree", "35")
    meta_list = local_manager.build_meta_list(local_meta)
    meta_tree = local_manager.build_tree_config(local_tree, local_types)

    # color_log("Step 3: ", "32")


if __name__ == "__main__":
    meta_builder = MetaBuilder()
