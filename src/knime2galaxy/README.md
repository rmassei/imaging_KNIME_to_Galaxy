# Structure 

knime2galaxy/
├── main.py                         # Einstiegspunkt: orchestriert alles
├── config/
│   └── translation_table.yml      # Mapping-Tabelle KNIME → Galaxy
├── llm/
│   └── llm_endpoints.py           # LLM-Schnittstelle
├── parser/
│   ├── knime_parser.py            # Extrahiert Nodes aus .knwf/.knime
│   └── utils.py                   # Unzip die Datei
├── generator/
│   ├── galaxy_tool_builder.py     # Erzeugt tool.xml + script.py
│   ├── workflow_writer.py         # Verknüpft Tools zu .ga Workflow
├── models/
│   ├── node.py                    # KNIMENode, GalaxyTool – interne Repräsentationen
│   └── mapping.py                 # Strukturen für die Übersetzung (evtl. mit pydantic)
├── test_data/
│   └── example.knwf               # Testbeispiel
├── output/
│   ├── tools/
│   └── workflows/
├── tests/
│   └── test_mapping.py
└── README.md

# Data Flow

KNIME Workflow (.knwf)
    ↓
[knime_parser.py]
    ↓
KNIMENode-Objekte (XML → dict)
    ↓
[llm_endpoints.py]
    ↓
GalaxyTool-Definition (via LLM)
    ↓
[galaxy_tool_builder.py]
    ↓
tool.xml + script.py
    ↓
[workflow_writer.py]
    ↓
Workflow.gx
