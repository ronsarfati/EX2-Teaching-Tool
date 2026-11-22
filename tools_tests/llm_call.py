"""One short real call to the Anthropic API (key from env var ANTHROPIC_API_KEY or repo-root .env).

Run:  python tools_tests/llm_call.py <text_file_outside_repo> [model]
Prints model, latency and token usage only. Never prints the key.
"""
import os
import pathlib
import sys
import time


def load_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    env = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY=") and line.split("=", 1)[1].strip():
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
                return True
    return False


def main(text_file, model):
    if not load_key():
        print("NO KEY: ANTHROPIC_API_KEY not set (env or .env) - test pending")
        return
    import anthropic

    text = pathlib.Path(text_file).read_text(encoding="utf-8")[:3000]
    client = anthropic.Anthropic()
    t0 = time.perf_counter()
    msg = client.messages.create(
        model=model, max_tokens=300,
        messages=[{"role": "user", "content": "Summarise this lecture excerpt in 3 bullet points:\n\n" + text}],
    )
    dt = time.perf_counter() - t0
    print(f"model={msg.model} latency_s={dt:.1f} input_tokens={msg.usage.input_tokens} "
          f"output_tokens={msg.usage.output_tokens} stop={msg.stop_reason} chars_out={len(msg.content[0].text)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-5-5")
