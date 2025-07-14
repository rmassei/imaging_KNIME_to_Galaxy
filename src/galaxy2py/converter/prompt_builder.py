def build_prompt(json_str: str) -> str:
    return f"""
You are an expert in bioimage analysis and Jupyter notebooks.

Translate the following Galaxy workflow (in JSON format) into a clean Python Jupyter notebook that executes the same sequence of analysis steps.

Use standard tools like BioPython, NumPy, scikit-image, Cellpose or napari as appropriate.

Input:
```json
{json_str}
"""