"""Model-independent generation. Providers: none (extractive), openai_compatible, ollama, hf."""
from __future__ import annotations
import re, httpx, os
from common import load_config

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")
_STOPQ = set("what which who how why does do is are the of in on for to a an and or between versus vs compare comparison evidence latest recent papers paper".split())


class LLM:
    name = "none"
    def generate(self, prompt: str, max_tokens=700) -> str: raise NotImplementedError


class OpenAICompatible(LLM):
    def __init__(self, base_url, model, api_key_env="OPENAI_API_KEY"):
        self.base_url, self.model, self.key = base_url.rstrip("/"), model, os.environ.get(api_key_env, "none"); self.name = f"openai_compatible:{model}"
    def generate(self, prompt, max_tokens=700):
        r = httpx.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.key}"}, timeout=120,
                       json={"model": self.model, "temperature": 0.1, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]


class Ollama(LLM):
    def __init__(self, base_url, model): self.base_url, self.model = base_url.rstrip("/"), model; self.name = f"ollama:{model}"
    def generate(self, prompt, max_tokens=700):
        r = httpx.post(f"{self.base_url}/api/generate", timeout=300, json={"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1, "num_predict": max_tokens}})
        r.raise_for_status(); return r.json()["response"]


class HFLocal(LLM):
    def __init__(self, model):
        self.model_name, self._p = model, None; self.name = f"hf:{model}"
    def generate(self, prompt, max_tokens=700):
        if self._p is None:
            from transformers import pipeline
            from common import get_device
            self._p = pipeline("text-generation", model=self.model_name, device=get_device())
        return self._p(prompt, max_new_tokens=max_tokens, do_sample=False, return_full_text=False)[0]["generated_text"]


class Extractive(LLM):
    """No generative model: select the most query-relevant sentences verbatim from the cited passages.
    Cannot hallucinate; also less fluent. Used by default when no LLM is configured."""
    name = "extractive"
    def generate(self, prompt, max_tokens=700): raise RuntimeError("use .answer()")

    def answer(self, question: str, citations: dict[int, dict], max_sentences=5) -> str:
        q = {w for w in re.findall(r"[a-z0-9]{3,}", question.lower()) if w not in _STOPQ}
        scored, seen = [], set()
        for n, c in citations.items():
            for s in _SENT.split(c["passage"].replace("\n", " ")):
                s = s.strip()
                if len(s) < 40 or s.lower() in seen: continue
                seen.add(s.lower())
                w = set(re.findall(r"[a-z0-9]{3,}", s.lower()))
                scored.append((len(q & w) / (len(q) or 1) + 0.002 * min(len(s), 200) / 200 - 0.01 * n, n, s))
        scored.sort(key=lambda x: -x[0])
        picks = [t for t in scored[:max_sentences] if t[0] > 0.05]
        return " ".join(f"{s.rstrip('.')} [{n}]." for _, n, s in picks)


def get_llm(provider: str | None = None) -> LLM:
    cfg = load_config("models")["llm"]
    p = provider or cfg["provider"]
    if p == "openai_compatible": return OpenAICompatible(**cfg["openai_compatible"])
    if p == "ollama": return Ollama(**cfg["ollama"])
    if p == "hf": return HFLocal(**cfg["hf"])
    return Extractive()
