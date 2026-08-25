from app import create_app

app = create_app()

if __name__ == "__main__":
    # host=0.0.0.0/port=5050 - port 5000 is squatted by macOS's AirPlay
    # Receiver on this machine, and 0.0.0.0 (not the 127.0.0.1 default) is
    # what makes the dev server reachable from a phone on the same LAN.
    # threaded=True matters more than it looks: Werkzeug's dev server
    # handles one request at a time without it, and a mobile browser's
    # keep-alive/prefetch connections can then block out every other
    # request (including the next reload) until that connection is
    # released - looked exactly like "loads once or twice, then never
    # again" (Adi's report, 2026-08-25), while a desktop browser hitting it
    # differently didn't trigger the same stall. use_reloader=False avoids
    # Werkzeug's monitor+worker process pair, which has its own failure
    # mode (an orphaned worker silently serving stale code after a kill -
    # see docs/PROJECT_STATUS.md's translation-bug entries).
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True, use_reloader=False)
