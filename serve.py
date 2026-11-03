"""Finance App V2, release runtime (P6 step 3): the app on Waitress, a pure-Python production WSGI server.

Local by default: it listens on 127.0.0.1 only, so nothing outside this computer can reach it. HOST, PORT and THREADS
change that (see README "Run"). Development stays `python app.py` (Flask's own server, for local work only).

    python serve.py            check the settings and data files, then serve (Ctrl+C stops it)
    python serve.py --check    only check, then exit: 0 = ready, 1 = a problem (nothing is started or written)
"""
import logging
import sys

USAGE = "Usage: python serve.py [--check]"


def main(argv):
    if argv not in ([], ["--check"]):
        print(USAGE, file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    import config
    from services import startup
    problems = startup.check()
    if problems:
        print("Finance App V2 cannot start:", file=sys.stderr)
        for problem in problems:
            print("  - " + problem, file=sys.stderr)
        return 1
    url = f"http://{config.HOST}:{config.PORT}"
    exposure = ("only on this computer" if startup.is_loopback(config.HOST)
                else "ON THE NETWORK: other computers that can reach this one can open it")
    if argv == ["--check"]:
        print(f"Ready: settings and data files are valid. It would serve {url} ({exposure}).")
        return 0
    from waitress import serve
    from app import create_app
    app = create_app()
    print(f"Finance App V2 on {url} ({exposure}). Zero-cost mode: {'on' if config.ZERO_COST_MODE else 'OFF'}. "
          "Press Ctrl+C to stop.", flush=True)
    try:
        serve(app, host=config.HOST, port=config.PORT, threads=config.THREADS, ident="")
    except OSError as exc:
        print(f"Finance App V2 cannot listen on {config.HOST}:{config.PORT} ({exc.strerror or exc}). Is something "
              "else using that port? Set PORT to another number.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    print("Finance App V2 stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
