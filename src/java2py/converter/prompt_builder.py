def build_prompt(java_code: str) -> str:
    return f"""Translate the following Java code into pure, executable Python 3 code.

Instructions:
- Only output valid Python code.
- Do NOT include any comments (lines starting with #).
- Do NOT include Markdown formatting (like ```python).
- Do NOT add explanations or text before or after the code.
- Do NOT include any import statements, other than those that are necessary for the code to run.
- Just give the code. Nothing else.

This is the Java code to translate:
{java_code}

Only return Python code. Do not include any extra text or formatting.
"""

