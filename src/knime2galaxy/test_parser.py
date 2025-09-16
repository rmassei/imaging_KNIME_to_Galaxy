from parser.knime_parser import collect_knime_node_files

def main():
    workflow_dir = "test_data/unzipped_example/2024_nuclei_segmentation_knime"  # Ordnername wie bei dir

    node_files = collect_knime_node_files(workflow_dir)

    print(f"🔍 Gefundene Nodes: {len(node_files)}\n")

    for node_name, xml in node_files.items():
        print(f"📦 Node: {node_name}")
        print(f"🔹 XML-Vorschau: {xml[:300]}...\n")  # Nur die ersten 300 Zeichen anzeigen

if __name__ == "__main__":
    main()