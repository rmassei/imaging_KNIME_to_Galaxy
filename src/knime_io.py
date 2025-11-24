import json
import zipfile
from pathlib import Path

def load_tools_metadata(path: str | Path) -> dict:
    """
    Loads and returns tool metadata from a JSON file.

    path: Path to the JSON file.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def collect_knime_node_files(knwf_path: str) -> dict:
    """
    Collects all node settings.xml files inside the KNIME .knwf archive.
    Returns a dictionary: {node_folder_name: xml_content}.
    """
    node_data = {}
    with zipfile.ZipFile(knwf_path, "r") as zf:
        for file_name in zf.namelist():
            if file_name.endswith("settings.xml"):
                with zf.open(file_name) as f:
                    xml_content = f.read().decode("utf-8")
                    node_name = file_name.split("/")[-2]  # Ordnername
                    node_data[node_name] = xml_content
    return node_data