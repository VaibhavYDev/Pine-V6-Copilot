"""One explicitly authorized writer request that reports the provider's finish_reason. Never run by default."""
import argparse
import os
import sys
from getpass import getpass

from config import writer_model
from llm.client import ModelCallError, chat
from pipeline.answer import APP_TIMEOUT, MAX_TOKENS

PROBE_MESSAGES = [{"role": "user", "content": "Reply with exactly the word READY."}]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send one writer-model request and report its finish_reason.")
    parser.add_argument("--authorize-one-live-call", action="store_true")
    if not parser.parse_args(argv).authorize_one_live_call:
        parser.error("No request sent. Pass --authorize-one-live-call only after setting provider spending limits.")

    # Typed rather than exported, so the key stays out of shell history; config.py reads it in this process only.
    os.environ["CHAT_API_KEY"] = getpass("Writer API key (not shown or saved): ").strip()
    try:
        # The pipeline's own output limit and timeout, so "length" here means real drafts would be cut short too.
        reply = chat(PROBE_MESSAGES, writer_model(), max_tokens=MAX_TOKENS, temperature=0.0, timeout=APP_TIMEOUT)
    except (RuntimeError, ModelCallError) as error:
        # config.py and llm/client.py messages name settings, never their values, the key or the prompt.
        print(f"No reply: {error}")
        return 1
    finally:
        os.environ.pop("CHAT_API_KEY", None)

    # The reply text is never printed.
    print("model:", reply.model)
    print("finish_reason:", repr(reply.finish_reason))
    print("input_tokens:", reply.input_tokens)
    print("output_tokens:", reply.output_tokens)
    print("provider_requests:", reply.attempts)
    print("latency_ms:", reply.latency_ms)
    if reply.finish_reason != "stop":
        print("Not complete: the pipeline takes code only from a reply whose finish_reason is 'stop'.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
