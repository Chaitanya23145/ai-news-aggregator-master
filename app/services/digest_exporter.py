import os
import logging
from datetime import datetime
from app.config import DIGEST_OUTPUT_DIR

logger = logging.getLogger(__name__)


class DigestExporter:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or DIGEST_OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def export_digest(self, digest_result, date_str: str = None) -> dict:
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        md_filename = f"digest_{date_str}.md"
        html_filename = f"digest_{date_str}.html"

        md_path = os.path.join(self.output_dir, md_filename)
        html_path = os.path.join(self.output_dir, html_filename)

        # Get markdown content
        if hasattr(digest_result, "to_markdown"):
            markdown_content = digest_result.to_markdown()
        else:
            markdown_content = str(digest_result)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Also save latest symlink/file
        latest_md = os.path.join(self.output_dir, "latest.md")
        with open(latest_md, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info(f"Exported digest to {md_path} and {latest_md}")

        return {
            "markdown_path": md_path,
            "latest_path": latest_md,
            "date": date_str,
        }
