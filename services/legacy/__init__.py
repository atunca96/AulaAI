import logging
logger = logging.getLogger(__name__)

# LEGACY - DO NOT USE
# TO BE REMOVED AFTER VALIDATION
from .pdf_pipeline import process_pdf_to_classroom

def process(file_path):
    logger.warning("LEGACY PIPELINE IN USE")
    # Wrapper for legacy process
    return process_pdf_to_classroom(file_path, "0-0", "system")
