def build_summary_prompt(knime_nodes_str, workflow_content):
    
    summary_prompt = f"""
# Your Task
You are a rigorous workflow graph extractor and validator.
Your job is to read KNIME workflow XML and produce a clean structural summary of how nodes are connected,
so that the workflow can later be converted into a Galaxy (.ga) workflow.

You must also detect structural and semantic validation errors in the workflow (e.g. missing outputs, invalid connections, type mismatches).
You must not hallucinate any connections, nodes, or ports.
Respond only with valid JSON in the format below — no free text, no comments.

# Input
KNIME Nodes (XML):
```xml
{knime_nodes_str}
```

The KNIME workflow content (XML):
```xml
{workflow_content}
```

# Core Extraction Rules
- Extract every node (<node id="...">) with: id, label or name, kind (default: "op"), all explicit or implied input/output ports (from connections).
- Extract every data connection (<connection sourceID="..." sourcePort="..." destID="..." destPort="..."/>).
- Derive: "entry" = nodes with no incoming edges, "exit" = nodes with no outgoing edges
- Maintain stable node IDs — do not renumber.

# Validation Rules 
You must verify workflow consistency before outputting the final graph.
Report any violations in "validation_errors" with "severity", "rule", "message", and "evidence".
Input-type correctness

Nodes of type "data_input" do not produce outputs.

If another node references an "output" from a data_input, this is invalid → mark as "invalid_reference".

Expected fix: change the node type to "data_collection_input" or define an explicit output field.

Output-definition completeness

Any node that appears as a connection source must define at least one output.

If no output definition exists, mark as "missing_output_definition".

Connection validity

Every edge must reference an existing (node, port) pair.

If the referenced node or port does not exist, mark as "invalid_reference".

Type compatibility

Check that connected nodes have compatible data types (e.g. data_input → data_collection_input is invalid).

If the types differ in an incompatible way, mark as "type_mismatch".

Referential integrity

Each "output_name" in a connection must exist in the "outputs" list of the source node.

Each "input_name" must have a valid upstream output.

Also describe in words how the nodes are connected and what the workflow does. 

"""
    
    return summary_prompt

def build_description_task_prompt(knime_nodes_str, workflow_content, summary_answer):
    
    description_task_prompt = f"""
You will receive a KNIME workflow in JSON format.
For each node (step) in the workflow, write a 3 to 5 sentences description 
of what that node does, using simple technical verbs (e.g. trim, filter, convert, normalize, cluster).

Separate each node description with a semicolon (;).
Do not number the items or add any extra text.


Here is the KNIME workflow:
# Input
KNIME Nodes (XML):
```xml
{knime_nodes_str}
```

The KNIME workflow content (XML):
```xml
{workflow_content}
```

This KNIME graph:
{summary_answer}

Output Requirements:
- Separate each node description with a semicolon (;).
- Do not number the items or add any extra text.
- Use no special characters.


"""
    
    return description_task_prompt

def build_task_prompt(knime_nodes_str, workflow_content, summary_answer, input_tools, hits):
    
    task_prompt = f"""
# Your Task
You are a system that translates complete KNIME workflows into Galaxy workflows. Produce a **single, valid Galaxy .ga workflow JSON** that can be imported in Galaxy, representing the entire KNIME workflow below.

# Input
KNIME Nodes (XML):
```xml
{knime_nodes_str}
```

The KNIME workflow content (XML):
```xml
{workflow_content}
```

This KNIME graph:
{summary_answer}

The input node descriptions could be one of the following:
{input_tools}

# Output Requirements
- Respond with the complete Galaxy workflow JSON object ONLY (no markdown fences, no comments, no explanations).
- The JSON must be a valid Galaxy .ga workflow 
- Make sure that it is a valid JSON object.
- For uuid fields, write 00000000-0000-0000-0000-000000000000 as placeholder
- Do not include TODOs or comments in the JSON.
- Do not add anything in there that is not part of the Galaxy workflow JSON format
- Get the tool ids, content ids and versions correct based on the following knowledge base of Galaxy tools:

{hits}

- Use type: "data_input" only for a single dataset that is consumed by inputs expecting a single dataset.
- Use type: "data_collection_input" only when any downstream input expects a collection (e.g., list or list:paired).
- Never connect a data_input as a source if the downstream port expects a collection.
- Never invent an "output" on data_input. If an edge would reference such an output, remove that edge and proceed only with valid edges.


- Return a single JSON object and nothing else.

"""
    
    return task_prompt