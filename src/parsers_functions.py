import json
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

## KNIME PARSERS
def extract_knime_workflow(knwf_file, output_dir):
    """
    Unzip a KNIME.knwf worflow
    """
    with zipfile.ZipFile(knwf_file, 'r') as zip_ref:
        zip_ref.extractall(output_dir)
    print(f"Extracted {knwf_file} to {output_dir}")


def parse_knime_xml(xml_data, output_path):
    """
    Parse the KNIME workflow
    """
    tree = ET.parse(xml_data)
    root = tree.getroot()
    namespace = {'ns': 'http://www.knime.org/2008/09/XMLConfig'}

    nodes = []
    for node in root.findall(".//ns:config[@key='nodes']/ns:config", namespace):
        node_id = node.find(".//ns:entry[@key='id']", namespace).get('value')
        node_settings_file = node.find(".//ns:entry[@key='node_settings_file']", namespace).get('value')
        node_name = node_settings_file.split('/')[0].strip()
        nodes.append({"Node Number": node_id, "Node Name": node_name})

    df = pd.DataFrame(nodes)
    df.to_csv(f"{output_path}/parsed_KNIME_nodes.tsv", sep="\t")


## GALAXY PARSERS
def parse_galaxy_workflow(json_file, output_path):
    """
    Parses a Galaxy workflow JSON
    """
    with open(json_file, 'r') as file:
        data = json.load(file)

    steps_data = data.get("steps", {})
    steps = []

    for step_id, step in steps_data.items():
        step_info = {
            "Step ID": step_id,
            "Label": step.get("label"),
            "Name": step.get("name"),
            "Tool ID": step.get("tool_id"),
            "Type": step.get("type"),
            "UUID": step.get("uuid"),
        }
        steps.append(step_info)

    steps_df = pd.DataFrame(steps)
    steps_df.to_csv(f"{output_path}/parsed_Galaxy_workflow_steps.tsv", sep="\t", index=False)

    connections = []
    for step_id, step in steps_data.items():
        input_connections = step.get("input_connections", {})
        for input_name, conn in input_connections.items():
            connection_info = {
                "Source Step ID": conn["id"],
                "Source Output Name": conn["output_name"],
                "Destination Step ID": step_id,
                "Destination Input Name": input_name,
            }
            connections.append(connection_info)

    connections_df = pd.DataFrame(connections)
    connections_df.to_csv(f"{output_path}/Galaxy_workflow_connections.tsv", sep="\t", index=False)