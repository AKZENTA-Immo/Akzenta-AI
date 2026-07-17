import json
from typing import Any

from starlette.responses import JSONResponse

from backend.services.text_normalizer import normalize_api_data


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            normalize_api_data(content),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
