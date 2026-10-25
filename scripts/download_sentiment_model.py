"""One-time, explicit download of ProsusAI/finbert for the optional Sentiment Explorer (offline only).

Downloads only the files the app needs (safetensors weights, config, tokenizer) into the default
Hugging Face cache, which is outside this repository. The app itself never downloads: it loads with
local_files_only=True. Weights are CC BY-NC-SA 4.0 (non-commercial). Requires requirements-sentiment.txt.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config  # noqa: E402

FILES = ["config.json", "model.safetensors", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt"]


def main():
    from huggingface_hub import snapshot_download  # optional dependency

    path = snapshot_download(config.SENTIMENT_MODEL, allow_patterns=FILES)
    print(f"downloaded {config.SENTIMENT_MODEL} ({', '.join(FILES)}) to the Hugging Face cache: {path}")


if __name__ == "__main__":
    main()
