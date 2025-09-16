import yaml
from functools import lru_cache

@lru_cache(maxsize=1)
def load_translation_examples(yaml_path: str = "data/translation_table.yml") -> list:
    with open(yaml_path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
        print(docs)
        examples = []
        for doc in docs[0]:
            knime = doc.get("KNIME")
            galaxy = doc.get("Galaxy")

            if knime and galaxy:
                examples.append({
                    "KNIME": knime.strip(),
                    "Galaxy": galaxy.strip()
                })

    return examples

def build_prompt(source: str) -> str:
    examples_text =  """You are a translator that converts KNIME workflow nodes to Galaxy workflow steps.

Below are examples of how this translation should be done:
"""
    examples = load_translation_examples()
    if examples:
        for i, ex in enumerate(examples[:6]):  # z. B. nur 6 Beispiele
            examples_text += f"""

## Example {i + 1}:

KNIME node (XML):

```xml
{ex["KNIME"]}
```

Galaxy step (JSON):
```json
{ex["Galaxy"]}
```

# Your task:
KNIME Node:
```xml
{source}
```

Please give me the corresponding Galaxy step.
Respond with the Galaxy step only, without any additional text or comments.

"""
    return examples_text