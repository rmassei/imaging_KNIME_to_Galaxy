import os
import zipfile

def unzip_knime_workflow(zip_path: str, extract_to: str):
    """
    Entpackt eine KNIME .knwf Datei in das angegebene Zielverzeichnis.
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"✅ Entpackt: {zip_path} → {extract_to}")

def find_workflow_dir(base_dir: str) -> str:
    """
    Sucht im Verzeichnis base_dir nach dem ersten Unterordner, der eine Datei namens 'workflow.knime' enthält.
    Gibt dann den vollständigen Pfad zu diesem Unterordner zurück.
    """
    for entry in os.listdir(base_dir):  # Alle Dateien und Ordner in base_dir durchgehen
        full_path = os.path.join(base_dir, entry)

        # Wenn es ein Ordner ist und darin 'workflow.knime' liegt → Erfolg
        if os.path.isdir(full_path) and "workflow.knime" in os.listdir(full_path):
            return full_path

    # Wenn kein solcher Ordner gefunden wurde → Fehler auslösen
    raise ValueError(f"⚠️ Kein gültiger Workflow-Ordner gefunden in {base_dir}")