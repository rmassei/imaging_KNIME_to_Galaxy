from parser.knime_parser import collect_knime_node_files
from parser.utils import unzip_knime_workflow, find_workflow_dir
from llm.translator import Knime_to_Galaxy_Translator

def main(workflow_path):

    # 1. Workflow entpacken
    knwf_path = "test_data/2024_nuclei_segmentation_knime.knwf"
    extract_dir = "test_data_unzipped"

    unzip_knime_workflow(knwf_path, extract_dir)

    # 2. Workflow-Verzeichnis finden
    workflow_dir = find_workflow_dir(extract_dir)
    print(f"✅ Workflow-Verzeichnis gefunden: {workflow_dir}")

    # 3. KNIME-Nodes extrahieren
    knime_nodes = collect_knime_node_files(workflow_dir)

    translator = Knime_to_Galaxy_Translator()

    for node_name, xml in knime_nodes.items():
        print(translator.translate_code(xml))
        break




    # print(f"\n✅ {len(knime_nodes)} Nodes gefunden im Workflow:\n")
    # for node_name, xml in knime_nodes.items():
    #     print(f"📦 {node_name}")
    #     print(f"🔹 XML-Vorschau:\n{xml[:400]}...\n")

    # 4. LLM-Übersetzung der Nodes in Galaxy-Tools
    translator = Knime_to_Galaxy_Translator()

    # # 2. Für jeden Node: LLM-gestützte Übersetzung in Galaxy Toolstruktur
    # galaxy_tools = []
    # for node in knime_nodes:
    #     tool_def = query_llm_translation(node)
    #     galaxy_tools.append(tool_def)

    # # 3. Tools generieren
    # for tool in galaxy_tools:
    #     build_tool(tool)

    # # 4. Workflow generieren
    # build_workflow(galaxy_tools)

if __name__ == "__main__":
    main("test_data/example.knwf")