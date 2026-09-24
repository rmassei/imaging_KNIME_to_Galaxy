import json
import os
import uuid
import zipfile
from pathlib import Path, PurePosixPath


def _strip_common_archive_root(file_names: list[str], file_name: str) -> str:
    """
    Removes the single top-level workflow folder used by KNWF archives.
    """
    path_parts = PurePosixPath(file_name).parts
    roots = {
        PurePosixPath(name).parts[0]
        for name in file_names
        if PurePosixPath(name).parts
    }

    if len(roots) == 1 and len(path_parts) > 1:
        return str(PurePosixPath(*path_parts[1:]))

    return file_name


def load_tools_metadata(path: str | Path) -> dict:
    """
    Loads and returns tool metadata from a JSON file.

    path: Path to the JSON file.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect_knime_node_files(knwf_path: str) -> dict:
    """
    Collects all node settings.xml files inside the KNIME .knwf archive.
    Returns a dictionary: {node_path: xml_content}.
    """
    node_data = {}
    with zipfile.ZipFile(knwf_path, "r") as zf:
        file_names = zf.namelist()
        for file_name in sorted(file_names):
            if file_name.endswith("settings.xml"):
                with zf.open(file_name) as f:
                    xml_content = f.read().decode("utf-8")
                    relative_file_name = _strip_common_archive_root(
                        file_names, file_name
                    )
                    node_path = PurePosixPath(relative_file_name).parent.as_posix()
                    node_data[node_path] = xml_content
    return node_data


def collect_workflow_file(knwf_path: str) -> str:
    """
    Extracts workflow.knime content inside the KNIME .knwf archive.
    Nested workflow.knime files from components and metanodes are included too.
    Returns the file content as a string.
    """
    workflow_data = []
    with zipfile.ZipFile(knwf_path, "r") as zf:
        file_names = zf.namelist()
        for file_name in sorted(file_names):
            if file_name.endswith("workflow.knime"):
                with zf.open(file_name) as f:
                    workflow_content = f.read().decode("utf-8")
                    relative_file_name = _strip_common_archive_root(
                        file_names, file_name
                    )
                    workflow_data.append((relative_file_name, workflow_content))

    if len(workflow_data) == 1:
        return workflow_data[0][1]

    if workflow_data:
        return "\n\n".join(
            f"Workflow file: {file_name}\n{content}"
            for file_name, content in workflow_data
        )

    raise FileNotFoundError("workflow.knime not found in KNWF archive")


def convert_knime_dict_to_string(node_data: dict) -> str:

    knime_nodes_str = "\n".join(
        f"Node ID: {key}\n{value}" for key, value in node_data.items()
    )

    return knime_nodes_str


def load_galaxy_input_tools(input_tools_path: str):
    with open(input_tools_path, encoding="utf-8") as f:
        input_tools = json.load(f)

    return input_tools


def parse_answer_as_json(answer):
    try:
        json_object = json.loads(answer)
        return json_object
    except json.JSONDecodeError as e:
        raise ValueError("Failed to parse JSON:", e) from e


def replace_uuid(json_object):
    if "uuid" in json_object:
        json_object["uuid"] = str(uuid.uuid4())

    for step in json_object["steps"].values():
        if isinstance(step, dict) and "uuid" in step:
            step["uuid"] = str(uuid.uuid4())

    return json_object


def save_answer_to_file(json_object, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_object, f, indent=2, ensure_ascii=False)
