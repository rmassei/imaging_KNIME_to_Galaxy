import os

def collect_knime_node_files(workflow_dir: str):
    """
    Sammelt alle settings.xml-Dateien aus den Node-Unterordnern und gibt sie als dict zurück.
    Key: Node-Name (z. B. "Image Reader (#1)")
    Value: XML-String
    """
    node_data = {}

    for entry in os.listdir(workflow_dir):
        full_path = os.path.join(workflow_dir, entry)
        if os.path.isdir(full_path) and not entry.startswith('.'):
            xml_path = os.path.join(full_path, "settings.xml")
            if os.path.exists(xml_path):
                with open(xml_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                    node_data[entry] = xml_content

    return node_data