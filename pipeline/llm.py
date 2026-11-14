"""LLM access behind one small interface, with an on-disk cache.

Every call is keyed on (model, effort, prompt version, system, content, schema). A rerun
of the pipeline reuses earlier answers, so re-running after a code fix costs nothing,
and every answer stays on disk next to the work folder for audit.
"""
import base64
import hashlib
import json
import os
import time


class LLMError(RuntimeError):
    pass


class Provider:
    """generate_json(system, content, schema, model, effort) -> (dict, usage dict)
    content: list of {"text": str} or {"image_png": bytes}"""
    name = "base"

    def generate_json(self, system, content, schema, model, effort):
        raise NotImplementedError


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self):
        import anthropic
        self._anthropic = anthropic
        # credentials: ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / `ant auth login` profile
        self.client = anthropic.Anthropic(max_retries=4, timeout=600.0)

    def generate_json(self, system, content, schema, model, effort):
        blocks = []
        for part in content:
            if "image_png" in part:
                blocks.append({"type": "image", "source": {
                    "type": "base64", "media_type": "image/png",
                    "data": base64.standard_b64encode(part["image_png"]).decode("ascii")}})
            else:
                blocks.append({"type": "text", "text": part["text"]})
        # server-side fallback: if a safety classifier declines (rare on school math,
        # but possible), the API retries on a fallback model inside the same call
        resp = self.client.beta.messages.create(
            model=model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": blocks}],
            output_config={"effort": effort,
                           "format": {"type": "json_schema", "schema": schema}},
        )
        if resp.stop_reason == "refusal":
            raise LLMError(f"model declined: {getattr(resp, 'stop_details', None)}")
        if resp.stop_reason == "max_tokens":
            raise LLMError("output cut off at max_tokens")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise LLMError("no text block in response")
        usage = {"input_tokens": resp.usage.input_tokens,
                 "output_tokens": resp.usage.output_tokens,
                 "model": resp.model, "request_id": getattr(resp, "_request_id", None)}
        return json.loads(text), usage


class CachedLLM:
    def __init__(self, provider: Provider, cache_dir: str, prompt_version: str,
                 allow_calls: bool = True):
        self.provider = provider
        self.cache_dir = cache_dir
        self.prompt_version = prompt_version
        self.allow_calls = allow_calls
        self.calls = 0
        self.cache_hits = 0
        self.tokens_in = 0
        self.tokens_out = 0
        os.makedirs(cache_dir, exist_ok=True)

    def _key(self, system, content, schema, model, effort):
        h = hashlib.sha256()
        for part in (model, effort, self.prompt_version, system,
                     json.dumps(schema, sort_keys=True)):
            h.update(part.encode("utf-8")); h.update(b"\0")
        for part in content:
            if "image_png" in part:
                h.update(b"img:"); h.update(hashlib.sha256(part["image_png"]).digest())
            else:
                h.update(b"txt:"); h.update(part["text"].encode("utf-8"))
        return h.hexdigest()[:24]

    def generate_json(self, tag, system, content, schema, model, effort):
        """tag: a readable label stored with the cached answer (e.g. 'extract p003_b02')"""
        key = self._key(system, content, schema, model, effort)
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.isfile(path):
            self.cache_hits += 1
            with open(path, encoding="utf-8") as f:
                return json.load(f)["output"]
        if not self.allow_calls:
            raise LLMError(f"no cached answer for {tag} and LLM calls are disabled "
                           "(run with --yes to allow paid calls)")
        t0 = time.time()
        out, usage = self.provider.generate_json(system, content, schema, model, effort)
        self.calls += 1
        self.tokens_in += usage.get("input_tokens", 0)
        self.tokens_out += usage.get("output_tokens", 0)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tag": tag, "model": model, "effort": effort,
                       "prompt_version": self.prompt_version, "usage": usage,
                       "seconds": round(time.time() - t0, 1), "output": out},
                      f, ensure_ascii=False, indent=1)
        return out
