# converter/translator.py
from .llm_endpoints import prompt_scadsai_llm
from .prompt_builder import build_prompt

class JavaToPythonTranslator:
    def translate_code(self, java_code: str) -> str:
        prompt = build_prompt(java_code)
        return prompt_scadsai_llm(prompt)
