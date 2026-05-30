# Lessons Learned

- **FastAPI / Pydantic Settings Cache**: Changing `.env` variables does not automatically invalidate `@lru_cache` decorated `get_settings()` in a running FastAPI/uvicorn worker without a complete process reload/restart. Always ensure the process is fully terminated and restarted after modifying `.env`.
- **Buffered Python Output in Background Tasks**: Python buffers stdout by default when output is redirected to files/pipes in background commands. Always use `python3 -u` or flush `print(..., flush=True)` to ensure progress logs are written to disk immediately for troubleshooting.
- **Expensive LLM Fallbacks**: Avoid calling text-only LLMs on mock documents/inputs that don't have actual files on disk. Return mock/fallback structures instantly to save significant latency, API rate-limits, and token costs during automated evaluations.
