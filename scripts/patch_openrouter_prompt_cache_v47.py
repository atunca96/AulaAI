from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

# Cost-only optimization: keep lesson-generation calls on a stable OpenRouter
# session so repeated prompt prefixes can benefit from provider prompt caching.
# This intentionally changes no prompt text, model, temperature, token budget,
# schema, retry policy, validation logic, or publication audit semantics.
marker = '_AULAAI_LESSON_CACHE_SESSION_V47'
func_anchor = 'def _call_ai(messages: List[Dict], model: str = MODEL_STRUCTURAL, max_tokens: int = 1000, temperature: float = 0.7, json_mode: bool = True, allow_fallback: bool = True, usage_dict: Optional[Dict[str, Any]] = None) -> Optional[Dict]:\n'
if marker not in s:
    if func_anchor not in s:
        raise RuntimeError('v47 _call_ai anchor missing')
    prelude = "_AULAAI_LESSON_CACHE_SESSION_V47 = os.getenv('AULAAI_OPENROUTER_LESSON_SESSION') or ('aulaai-lesson-' + str(os.getpid()) + '-' + uuid.uuid4().hex[:12])\n\n"
    s = s.replace(func_anchor, prelude + func_anchor, 1)

payload_anchor = '''        req_payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
'''
payload_replacement = '''        req_payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if target_model == MODEL_LESSON:
            req_payload["session_id"] = _AULAAI_LESSON_CACHE_SESSION_V47
'''
if 'req_payload["session_id"] = _AULAAI_LESSON_CACHE_SESSION_V47' not in s:
    if payload_anchor not in s:
        raise RuntimeError('v47 request payload anchor missing')
    s = s.replace(payload_anchor, payload_replacement, 1)

usage_anchor = '''                                        usage_dict["model"] = target_model
                                        if "cost" in u_info and u_info["cost"] is not None:
'''
usage_replacement = '''                                        usage_dict["model"] = target_model
                                        _details = u_info.get("prompt_tokens_details") or {}
                                        _cached = _details.get("cached_tokens") or u_info.get("cached_tokens") or 0
                                        usage_dict["cached_tokens"] = usage_dict.get("cached_tokens", 0) + int(_cached)
                                        if "cost" in u_info and u_info["cost"] is not None:
'''
if 'usage_dict["cached_tokens"]' not in s:
    if usage_anchor not in s:
        raise RuntimeError('v47 usage anchor missing')
    s = s.replace(usage_anchor, usage_replacement, 1)

if s.count('req_payload["session_id"] = _AULAAI_LESSON_CACHE_SESSION_V47') != 1:
    raise RuntimeError('v47 session_id injection count invalid')
if marker not in s:
    raise RuntimeError('v47 session marker missing')

p.write_text(s, encoding='utf-8')
print('Applied v47 cost-only prompt cache; quality path unchanged')
