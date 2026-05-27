"""
AI Hub service layer implementation.
Provides Generate Text (gentxt) and Generate Image (genimg) capabilities using the OpenAI SDK.
"""

import base64
import io
import logging
import os
from typing import AsyncGenerator

import httpx
from core.config import settings
from openai import AsyncOpenAI
from schemas.aihub import GenImgRequest, GenImgResponse, GenTxtRequest, GenTxtResponse
from services.ai_usage import record_ai_usage

logger = logging.getLogger(__name__)


class InvalidImageInputError(ValueError):
    """Raised when the provided image input cannot be parsed."""


class AIHubService:
    """AI Hub service class that wraps LLM calls based on the OpenAI SDK."""

    def __init__(self):
        self.api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("APP_AI_KEY")
            or getattr(settings, "app_ai_key", "")
        ).strip()
        self.base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("APP_AI_BASE_URL")
            or getattr(settings, "app_ai_base_url", "")
        )
        self.default_model = (
            os.getenv("AI_DEFAULT_MODEL")
            or os.getenv("APP_AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "deepseek-chat"
        )
        self.vision_api_key = (os.getenv("VISION_API_KEY") or os.getenv("QWEN_API_KEY") or "").strip()
        self.vision_base_url = (
            os.getenv("VISION_BASE_URL")
            or os.getenv("QWEN_BASE_URL")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.vision_model = os.getenv("AI_VISION_MODEL") or os.getenv("VISION_MODEL") or "qwen3-vl-plus"
        if not self.vision_base_url.startswith(("http://", "https://")):
            logger.warning("Invalid VISION_BASE_URL %s, falling back to DashScope compatible endpoint", self.vision_base_url)
            self.vision_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        if not self.vision_model.startswith("qwen"):
            logger.warning("Invalid AI_VISION_MODEL %s, falling back to qwen3-vl-plus", self.vision_model)
            self.vision_model = "qwen3-vl-plus"

        if not self.base_url or not self.api_key:
            raise ValueError("AI service not configured. Set OPENAI_BASE_URL/OPENAI_API_KEY or APP_AI_BASE_URL/APP_AI_KEY.")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url.rstrip("/"),
            timeout=float(os.getenv("AI_REQUEST_TIMEOUT", "180")),
            http_client=httpx.AsyncClient(trust_env=False),
        )
        self.vision_client = None
        if self.vision_api_key and self.vision_base_url:
            self.vision_client = AsyncOpenAI(
                api_key=self.vision_api_key,
                base_url=self.vision_base_url.rstrip("/"),
                timeout=float(os.getenv("VISION_REQUEST_TIMEOUT", os.getenv("AI_REQUEST_TIMEOUT", "180"))),
                http_client=httpx.AsyncClient(trust_env=False),
            )

    def _resolve_model(self, requested_model: str | None) -> str:
        """Map legacy hard-coded model names to the configured provider model."""
        if not requested_model:
            return self.default_model
        if requested_model == "AI_DEFAULT_MODEL":
            return self.default_model
        if requested_model == "AI_VISION_MODEL":
            return self.vision_model
        legacy_prefixes = ("gemini-", "gpt-5", "gpt-4", "claude-")
        if requested_model.startswith(legacy_prefixes):
            return self.default_model
        return requested_model

    def _client_for_model(self, requested_model: str | None) -> AsyncOpenAI:
        """Route vision calls to the dedicated vision provider while keeping text calls unchanged."""
        resolved = self._resolve_model(requested_model)
        if (requested_model == "AI_VISION_MODEL" or resolved == self.vision_model) and self.vision_client:
            return self.vision_client
        return self.client

    def _is_vision_request(self, requested_model: str | None) -> bool:
        resolved = self._resolve_model(requested_model)
        return bool(self.vision_api_key and self.vision_base_url and (requested_model == "AI_VISION_MODEL" or resolved == self.vision_model))

    def _convert_message(self, msg) -> dict:
        """Convert message format and support multimodal content."""
        content = msg.content
        # If content is a list (multimodal), convert it to plain dicts
        if isinstance(content, list):
            content = [item.model_dump() if hasattr(item, "model_dump") else item for item in content]
        return {"role": msg.role, "content": content}

    async def gentxt(self, request: GenTxtRequest) -> GenTxtResponse:
        """
        Generate Text API (non-streaming), supports text and image input.

        Args:
            request: Generate text request parameters.

        Returns:
            Txt2TxtResponse: generated text response.
        """
        try:
            messages = [self._convert_message(msg) for msg in request.messages]

            model = self._resolve_model(request.model)
            if self._is_vision_request(request.model):
                async with httpx.AsyncClient(timeout=float(os.getenv("VISION_REQUEST_TIMEOUT", os.getenv("AI_REQUEST_TIMEOUT", "180"))), trust_env=False) as client:
                    response = await client.post(
                        f"{self.vision_base_url.rstrip('/')}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.vision_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": request.temperature,
                            "max_tokens": request.max_tokens,
                            "stream": False,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                content = data["choices"][0]["message"].get("content") or ""
                usage = data.get("usage")
            else:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=False,
                )

                content = response.choices[0].message.content or ""
                usage = None
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }

            await record_ai_usage(
                provider=(os.getenv("VISION_PROVIDER") or "qwen") if self._is_vision_request(request.model) else os.getenv("AI_PROVIDER", "openai-compatible"),
                model=model,
                module="aihub.gentxt",
                endpoint="chat/completions",
                usage=usage,
            )

            return GenTxtResponse(
                content=content,
                model=model,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"gentxt error: {e}")
            raise

    async def gentxt_stream(self, request: GenTxtRequest) -> AsyncGenerator[str, None]:
        """
        Generate Text API (streaming), supports text and image input.

        Args:
            request: Generate text request parameters.

        Yields:
            str: Generated text content chunk (plain text, not JSON).
        """
        try:
            messages = [self._convert_message(msg) for msg in request.messages]

            model = self._resolve_model(request.model)
            stream = await self._client_for_model(request.model).chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"gentxt_stream error: {e}")
            raise

    @staticmethod
    def _extract_image_ref(item: object) -> str:
        """
        Extract an image reference from an OpenAI-compatible genimg response item.

        Prefer `url` (to avoid huge response bodies); if url is not available, fall back to `b64_json`
        and wrap it as a base64 data URI.
        Compatible with both dict items and SDK object items.
        """
        if isinstance(item, dict):
            url = item.get("url")
            if url:
                return url
            b64_json = item.get("b64_json")
            if b64_json:
                return f"data:image/png;base64,{b64_json}"
        else:
            url = getattr(item, "url", None)
            if url:
                return url
            b64_json = getattr(item, "b64_json", None)
            if b64_json:
                return f"data:image/png;base64,{b64_json}"

        raise RuntimeError("Neither url nor b64_json found in genimg response item")

    @staticmethod
    def _parse_data_uri(data_uri: str) -> tuple[bytes, str]:
        """Parse a base64 data URI and return (bytes, content_type)."""
        if "," not in data_uri:
            raise InvalidImageInputError("Invalid data URI: missing ',' separator.")

        header, b64_data = data_uri.split(",", 1)
        content_type = "image/png"
        if header.startswith("data:"):
            meta = header[5:]
            # Typical header: "image/png;base64"
            if ";" in meta:
                maybe_type = meta.split(";", 1)[0].strip()
                if maybe_type:
                    content_type = maybe_type
            elif meta.strip():
                content_type = meta.strip()

        try:
            return base64.b64decode(b64_data), content_type
        except Exception as e:
            raise InvalidImageInputError("Invalid base64 data in data URI.") from e

    @staticmethod
    def _filename_from_content_type(content_type: str, name_prefix: str = "image") -> str:
        """Best-effort filename for in-memory uploads."""
        ct = (content_type or "").lower()
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/webp": "webp",
        }.get(ct, "png")
        return f"{name_prefix}.{ext}"

    async def _image_str_to_upload_file(self, image: str, name_prefix: str = "image") -> io.BytesIO:
        """
        Convert image input (base64 data URI) into an in-memory file object for uploads.

        The OpenAI `images.edit` endpoint expects multipart file uploads; we keep the API JSON-only
        by allowing clients to pass a base64 data URI, and converting it here.
        """
        image = (image or "").strip()
        if not image:
            raise InvalidImageInputError("Input image is empty.")

        if image.startswith(("http://", "https://")):
            raise InvalidImageInputError(
                "URL input is not supported for image editing. Use a base64 data URI like `data:image/png;base64,...`."
            )
        if not image.startswith("data:"):
            raise InvalidImageInputError(
                "Only base64 data URI is supported for image editing. Example: `data:image/png;base64,...`."
            )

        image_bytes, content_type = self._parse_data_uri(image)

        upload = io.BytesIO(image_bytes)
        # openai SDK uses this name for multipart filename
        upload.name = self._filename_from_content_type(content_type, name_prefix=name_prefix)  # type: ignore[attr-defined]
        return upload

    async def _image_input_to_upload_files(self, image_input: str | list[str]) -> list[io.BytesIO]:
        """
        Convert image input (single data URI or list of data URIs) into uploadable file objects.

        Some OpenAI-compatible `images/edits` implementations support multiple input images.
        """
        images = [image_input] if isinstance(image_input, str) else image_input
        if not images:
            raise InvalidImageInputError("Input image list is empty.")

        upload_files: list[io.BytesIO] = []
        for idx, img in enumerate(images):
            if not isinstance(img, str):
                raise InvalidImageInputError("Each image must be a base64 data URI string.")
            upload_files.append(await self._image_str_to_upload_file(img, name_prefix=f"image_{idx + 1}"))
        return upload_files

    async def genimg(self, request: GenImgRequest) -> GenImgResponse:
        """
        Generate Image API.

        Args:
            request: Generate image request parameters.

        Returns:
            GenImgResponse: generated image response, where `images` is a list of image refs (URL preferred; fallback to base64 data URI).
        """
        try:
            # If an input image is provided, use the image editing endpoint (img2img).
            if request.image:
                image_files = await self._image_input_to_upload_files(request.image)
                image_param = image_files[0] if len(image_files) == 1 else image_files
                response = await self.client.images.edit(
                    model=request.model,
                    image=image_param,
                    prompt=request.prompt,
                    size=request.size,
                    n=request.n,
                )
            else:
                response = await self.client.images.generate(
                    model=request.model,
                    prompt=request.prompt,
                    size=request.size,
                    quality=request.quality,
                    n=request.n,
                )

            revised_prompt = response.data[0].revised_prompt if response.data else None

            if not response.data:
                raise RuntimeError("Image generation returned empty result")

            # Prefer URL to avoid huge response bodies; fallback to base64 data URI.
            images = [self._extract_image_ref(item) for item in response.data]

            return GenImgResponse(
                images=images,
                model=request.model,
                revised_prompt=revised_prompt,
            )

        except Exception as e:
            logger.error(f"genimg error: {e}")
            raise
