# converter/translator.py
from .llm_endpoints import prompt_scadsai_llm
from .prompt_builder import build_prompt

class GalaxyToPythonTranslator:
    def translate_code(self, json_str: str) -> str:
        prompt = build_prompt(json_str)
        return prompt_scadsai_llm(prompt)
