"""PyInstaller entry point.  Having a real script (instead of `-m`) makes the
start-at-login command and the packaged executable consistent."""

from magically_encircle.app import main

if __name__ == "__main__":
    raise SystemExit(main())
