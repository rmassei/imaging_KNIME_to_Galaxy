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
- Name the workflow according to the contents of what it is doing
- The JSON must be a valid Galaxy .ga workflow 
- Make sure that it is a valid JSON object.
- For uuid fields, write 00000000-0000-0000-0000-000000000000 as placeholder
- Do not include TODOs or comments in the JSON.
- Do not add anything in there that is not part of the Galaxy workflow JSON format
- Get the tool ids, content ids and versions correct based on the following knowledge base of Galaxy tools:
- Name the workflow according its contents

{hits}

NEVER come up with own tool names, tool IDs, content IDs or versions on your own. ONLY use the ones provided from the previously given knowledge base.
If tools are invented, that are not existent, the whole workflow will fail. So it is very important to only use existent ones.

- Use type: "data_input" only for a single dataset that is consumed by inputs expecting a single dataset.
- Use type: "data_collection_input" only when any downstream input expects a collection (e.g., list or list:paired).
- Never connect a data_input as a source if the downstream port expects a collection.
- Never invent an "output" on data_input. If an edge would reference such an output, remove that edge and proceed only with valid edges.




- Return a single JSON object and nothing else.

"""
    
    return task_prompt


def build_report_prompt(
    record: dict,
    knwf_path: str,
    output_galaxy_workflow_path: str,
    knime_description: str,
    knime_workflow_content: str,
    ga_content: str,
    hits: list,
):

    report_prompt = f"""
You are an expert in writing reports about translation pipelines.

You will receive a record that was produced about a translation process, in which a KNIME workflow file (.knwf) was translated into a Galaxy workflow file (.ga).
The goal is to summarize what went wrong, if any errors occurred during testing or validation, based primarily on this record: {record}.

The original .knwf workflow content can be seen here: {knime_workflow_content}
The generated .ga workflow content can be seen here: {ga_content}

Use the KNIME and Galaxy workflow contents only to explain why the observed failures occurred and whether the generated workflow correctly represents the original workflow.

It is important to identify and explain any issues that prevent the generated .ga workflow from functioning correctly. Examples of issues to highlight include:
- tools that are not working correctly for their intended purpose
- hallucinated Galaxy tools (i.e., tools referenced in the .ga file that do not exist on the target Galaxy server)
- formatting or structural issues in the generated .ga file
- incorrect tool mappings between KNIME and Galaxy
- missing workflow components or connections
- parameter configuration errors

Do not speculate about failures that are not supported by the provided record, KNIME workflow, or Galaxy workflow. If information is missing, explicitly state that the cause could not be determined from the available data.

The report MUST be valid markdown (.md) and MUST have the following structure:

# Knime2Galaxy Translation Report

## Files
- **KNIME Workflow file**: *{knwf_path}*
- **Galaxy Output file**: *{output_galaxy_workflow_path}*

## Successful Steps
< IN BULLET POINTS: describe components that were translated correctly, tools that exist on the target Galaxy server, workflow sections that execute successfully, or workflow structures that correctly correspond to the original KNIME workflow. If no successful steps can be identified, explicitly state this. >

## Recommended Tools
< Go through this tools: {hits} and give a ONE SENTENCE explanation whether these tools are suitbale for the desired workflow or not> 

## Failures
< IN BULLET POINTS: describe what is not yet working, why the workflow is failing or producing errors, which tools are hallucinated / not installed / incorrectly configured, and any structural or formatting issues. Keep the explanation easy for the user to understand. If no failures are detected, explicitly state this. >

## Recommendation
< For each failure listed above, provide a corresponding corrective action. Clearly explain what the user needs to change in the .ga workflow to make it valid and better aligned with the original .knwf workflow. When possible, specify which tool, parameter, connection, or workflow element should be corrected or replaced. >

Don't output anything other than the Markdown structure above.
"""
    return report_prompt