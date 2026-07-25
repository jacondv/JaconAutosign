"""Save/load/manage templates in the app data directory (JSON, 1 file per template)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..models import Template


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "template"


class TemplateService:
    def __init__(self, templates_dir: Path):
        self._dir = templates_dir

    def _path_for(self, template_id: str) -> Path:
        return self._dir / f"{template_id}.json"

    def list_templates(self) -> list[Template]:
        templates = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                templates.append(self._load_path(path))
            except (json.JSONDecodeError, KeyError):
                continue  # skip a corrupt template file, don't fail the whole list
        return templates

    def load(self, template_id: str) -> Template:
        return self._load_path(self._path_for(template_id))

    def _load_path(self, path: Path) -> Template:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Template.from_dict(data)

    def save(self, template: Template) -> Template:
        if not template.template_id:
            template.template_id = self._unique_id(slugify(template.template_name))
        if not template.created_at:
            template.created_at = datetime.now(timezone.utc).astimezone().isoformat()
        path = self._path_for(template.template_id)
        path.write_text(
            json.dumps(template.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return template

    def delete(self, template_id: str) -> None:
        path = self._path_for(template_id)
        if path.exists():
            path.unlink()

    def duplicate(self, template_id: str, new_name: str) -> Template:
        original = self.load(template_id)
        new_template = Template.from_dict(original.to_dict())
        new_template.template_id = self._unique_id(slugify(new_name))
        new_template.template_name = new_name
        new_template.created_at = datetime.now(timezone.utc).astimezone().isoformat()
        return self.save(new_template)

    def _unique_id(self, base_slug: str) -> str:
        candidate = base_slug
        counter = 2
        while self._path_for(candidate).exists():
            candidate = f"{base_slug}-{counter}"
            counter += 1
        return candidate
