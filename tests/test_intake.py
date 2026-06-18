"""Tests for project intake file parsing."""

import json
import zipfile
from io import BytesIO

import pytest
from fastapi import UploadFile

from api.services.intake import parse_intake_upload
from shared.schemas.project_brief import ProjectType

BRIEF = {
    "project_name": "Test Tower",
    "address": "1 Congress Ave, Austin, TX 78701",
    "units": 10,
    "stories": 3,
    "gross_sqft": 12000,
    "lot_sqft": 20000,
    "parking_spaces": 15,
}


class _FakeUpload:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data

    async def read(self) -> bytes:
        return self._data


@pytest.mark.asyncio
async def test_parse_json_brief():
    upload = _FakeUpload("brief.json", json.dumps(BRIEF).encode())
    brief, _ = await parse_intake_upload(upload, ProjectType.MULTIFAMILY_RESIDENTIAL)  # type: ignore[arg-type]
    assert brief.project_name == "Test Tower"
    assert brief.units == 10


@pytest.mark.asyncio
async def test_parse_zip_brief():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("project_brief.json", json.dumps(BRIEF))
    upload = _FakeUpload("package.zip", buf.getvalue())
    brief, _ = await parse_intake_upload(upload, ProjectType.COMMERCIAL)  # type: ignore[arg-type]
    assert brief.project_name == "Test Tower"
    assert brief.project_type == ProjectType.COMMERCIAL
