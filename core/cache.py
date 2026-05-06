import json
import os
from ceo.orchestrator import run_analysis


def get_analysis_cached(ticker: str, use_cache: bool) -> dict:
    """
    Returns analysis for a ticker, reading from cache if requested.
    After a fresh analysis, saves the result to storage/{ticker}_analysis.json.
    """
    cache_file = f"storage/{ticker}_analysis.json"

    if use_cache and os.path.exists(cache_file):
        with open(cache_file) as f:
            cached = json.load(f)
        if cached.get("status") == "ok":
            print(f"📂 {ticker}: usando cache ({cached.get('date', 'fecha desconocida')})")
            return cached

    if use_cache and not os.path.exists(cache_file):
        print(f"⚠️  {ticker}: sin cache — omitido (corré sin --cache para analizar en vivo)")
        return {"status": "skipped", "ticker": ticker}

    print(f"🔍 Analizando {ticker}...")
    result = run_analysis(ticker)

    if result.get("status") == "ok":
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result
