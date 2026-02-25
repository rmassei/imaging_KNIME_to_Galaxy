from imaging_knime_to_galaxy.llm_client import prompt_scadsai_llm
from imaging_knime_to_galaxy.knime_io import load_tools_metadata, collect_knime_node_files, collect_workflow_file, convert_knime_dict_to_string, load_galaxy_input_tools, parse_answer_as_json, replace_uuid, save_answer_to_file
from imaging_knime_to_galaxy.Vectorstore import VectorStore
from imaging_knime_to_galaxy.rag_functions import build_all_docs, embed, search_store_for_hits
from imaging_knime_to_galaxy.examples import build_translation_examples, build_workflow_examples
from imaging_knime_to_galaxy.prompts import build_summary_prompt, build_description_task_prompt, build_task_prompt

def translate_knime_to_galaxy(
        knwf_path: str,
        tools_metadata_path: str,
        translation_table_path: str,
        workflow_examples_yml_path: str,
        output_galaxy_workflow_path: str
):
    meta_data = load_tools_metadata(tools_metadata_path)
    texts, metas = build_all_docs(meta_data)
    vector_store = VectorStore(
        embed_fn= embed, 
        texts=texts, 
        metadatas=metas)
    
    knime_nodes = collect_knime_node_files(knwf_path=knwf_path)
    workflow_content = collect_workflow_file(knwf_path)
    node_examples = build_translation_examples(yaml_path=translation_table_path)
    knime_nodes_str = convert_knime_dict_to_string(knime_nodes)

    summary_task = build_summary_prompt(knime_nodes_str, workflow_content)
    workflow_examples = build_workflow_examples(yaml_path=workflow_examples_yml_path)

    full_summary_prompt = f"{node_examples}\n\n{workflow_examples}\n\n{summary_task}"
    summary_answer = prompt_scadsai_llm(message= full_summary_prompt)
    description_task = build_description_task_prompt(knime_nodes_str, workflow_content, summary_answer)
    full_description_prompt = f"{node_examples}\n\n{workflow_examples}\n\n{description_task}"
    description = prompt_scadsai_llm(message= full_description_prompt)
    
    hits = search_store_for_hits(description, vector_store)
    input_tools = load_galaxy_input_tools()
    task = build_task_prompt(knime_nodes_str, workflow_content, summary_answer, hits, input_tools)
    full_prompt = f"{node_examples}\n\n{workflow_examples}\n\n{task}"

    answer = prompt_scadsai_llm(message= full_prompt)
    json_object = parse_answer_as_json(answer)
    replace_uuid(json_object)
    save_answer_to_file(json_object, output_path=output_galaxy_workflow_path)
