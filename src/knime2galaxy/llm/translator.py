# llm/translator.py
from .llm_endpoints import prompt_scadsai_llm
from .prompt_builder import build_prompt

class Knime_to_Galaxy_Translator:
    def translate_code(self, source: str) -> str:
        prompt = build_prompt(source)
        return prompt_scadsai_llm(prompt)
