from imaging_knime_to_galaxy.llm_client import prompt_scadsai_llm
from imaging_knime_to_galaxy.knime_io import load_tools_metadata, collect_knime_node_files, collect_workflow_file, convert_knime_dict_to_string, load_galaxy_input_tools, parse_answer_as_json, replace_uuid, save_answer_to_file
from imaging_knime_to_galaxy.Vectorstore import VectorStore
from imaging_knime_to_galaxy.rag_functions import build_all_docs, embed, search_store_for_hits, EMBEDDING_MODEL
from imaging_knime_to_galaxy.examples import build_translation_examples, build_workflow_examples
from imaging_knime_to_galaxy.prompts import build_summary_prompt, build_description_task_prompt, build_task_prompt, build_report_prompt
from imaging_knime_to_galaxy.evaluation_functions import add_missing_input_labels, generate_job_yaml, run_command, testing_report, extract_error_message
import os
from huggingface_hub import hf_hub_download
from pathlib import Path


def translate_knime_to_galaxy(
        knwf_path: str,
        tools_metadata_path: str,
        translation_table_path: str,
        workflow_examples_yml_path: str,
        output_galaxy_workflow_path: str,
        input_workflow_path: str,
        vector_store_path: str,
        example_image_path="../knime2galaxy_scheme.png",

):
    meta_data = load_tools_metadata(tools_metadata_path)
    texts, metas = build_all_docs(meta_data)
    # embedding model is the same as the pre-computed embeddings
    if EMBEDDING_MODEL == "Qwen/Qwen3-Embedding-4B":
        print("Embedding Model matches the default. Trying to load pre-computed embeddings ...")
        if os.path.exists(vector_store_path):
            print("Loading cached vector store...")
            vector_store = VectorStore.load(vector_store_path, embed_fn=embed)
        else:
            try:
                print("Local vector store not found. Trying Hugging Face...")
                
                downloaded_file = hf_hub_download(
                    repo_id="lea-33/galaxy_tool_vector_storage",
                    filename="vector_store.npz",
                    repo_type="dataset",
                )
        
                vector_store = VectorStore.load(downloaded_file, embed_fn=embed)
        
                # Save locally after loading
                print(f"Saving vector store under: {vector_store_path}")
                vector_store.save(vector_store_path)
        
            except Exception as e:
                print(f"Could not load vector store from Hugging Face: {e}")
                print("Building vector store...")
                
                vector_store = VectorStore(embed_fn=embed, texts=texts, metadatas=metas)
                vector_store.save(vector_store_path)
    # different embedding model
    else:
        print("Embedding Model does not match the default. Computing new embeddings ...")
        vector_store = VectorStore(embed_fn=embed, texts=texts, metadatas=metas)
        vector_store.save(vector_store_path)
            
    print("Processing KNIME file content ...")
    knime_nodes = collect_knime_node_files(knwf_path=knwf_path)
    workflow_content = collect_workflow_file(knwf_path)
    node_examples = build_translation_examples(yaml_path=translation_table_path)
    knime_nodes_str = convert_knime_dict_to_string(knime_nodes)

    print("Building prompts with translation examples ...")
    summary_task = build_summary_prompt(knime_nodes_str, workflow_content)
    workflow_examples = build_workflow_examples(yaml_path=workflow_examples_yml_path)

    full_summary_prompt = f"{node_examples}\n\n{workflow_examples}\n\n{summary_task}"
    summary_answer = prompt_scadsai_llm(message= full_summary_prompt)
    description_task = build_description_task_prompt(knime_nodes_str, workflow_content, summary_answer)
    full_description_prompt = f"{node_examples}\n\n{workflow_examples}\n\n{description_task}"
    print("Retrieving relevant tool suggestions from the pipeline ...")
    description = prompt_scadsai_llm(message= full_description_prompt)

    print("Search for the best matching tools available on Galaxy.eu ...")
    hits = search_store_for_hits(description, vector_store)
    input_tools = load_galaxy_input_tools(input_workflow_path)
    task = build_task_prompt(knime_nodes_str, workflow_content, summary_answer, hits, input_tools)
    full_prompt = f"{node_examples}\n\n{workflow_examples}\n\n{task}"

    print("Generating and processing the final Galaxy workflow file ...")
    answer = prompt_scadsai_llm(message= full_prompt)
    json_object = parse_answer_as_json(answer)
    replace_uuid(json_object)
    save_answer_to_file(json_object, output_path=output_galaxy_workflow_path)
    print(f"Saved .ga file to {output_galaxy_workflow_path}.")

    print("Evaluating result and generating report ...")
    record_dict = testing_report(output_galaxy_workflow_path, knwf_path, "job.yml", example_image_path)
    report_prompt = build_report_prompt(record_dict, knwf_path, output_galaxy_workflow_path, description, workflow_content, answer, hits)
    report = prompt_scadsai_llm(message= report_prompt)
    output_path = Path(output_galaxy_workflow_path)
    report_path = output_path.parent / f"report_{output_path.stem}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved under {report_path}.")