# Changeset 006 – Harden pptx_to_img conversion

This changeset improves the robustness of the `pptx_to_img.py` script:

* Imports `shutil` to check for the presence of the `soffice` (LibreOffice) executable using `shutil.which`.
* Validates that the input PPTX file exists and raises a `FileNotFoundError` if it does not.
* Wraps the `subprocess.run` call in a `try/except` block to catch `CalledProcessError` and raise a descriptive `RuntimeError` when conversion fails.

Rollback: Revert the changes to `pptx_to_img.py` to restore the previous behaviour without validation.