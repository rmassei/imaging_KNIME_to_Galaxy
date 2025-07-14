import sys
import nbformat
from nbformat.v4 import new_notebook, new_code_cell
from converter.translator import GalaxyToPythonTranslator

def save_to_notebook(python_code: str, output_path: str):
    nb = new_notebook()
    nb.cells.append(new_code_cell(python_code))
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

if __name__ == "__main__":
    api_key = "None"
    translator = GalaxyToPythonTranslator()

    try:
        input_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else "translated_code.ipynb"

        with open(input_path, 'r') as file:
             galaxy_json = file.read()

        python_code = translator.translate_code(galaxy_json)

        save_to_notebook(python_code, output_path)
        print(f"Translated code saved to {output_path}")
    except IndexError:
        print("Usage: python main.py <input.java> [output.ipynb]")
        sys.exit(1)
    except FileNotFoundError:
        print(f"File {sys.argv[1]} not found.")
        sys.exit(1)

