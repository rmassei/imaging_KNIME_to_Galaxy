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

def collect_workflow_file(knwf_path: str) -> str:
    """
    Extracts the content of the workflow.knime file inside the KNIME .knwf archive.
    Returns the file content as a string.
    """
    with zipfile.ZipFile(knwf_path, "r") as zf:
        for file_name in zf.namelist():
            if file_name.endswith("workflow.knime"):
                with zf.open(file_name) as f:
                    return f.read().decode("utf-8")
    raise FileNotFoundError("workflow.knime not found in KNWF archive")

def convert_knime_dict_to_string(node_data: dict) -> str:
    
    knime_nodes_str = "\n".join(
    f"Node ID: {key}\n{value}" for key, value in node_data.items())

    return knime_nodes_str
