"""
Loads variables from .env into the process environment as soon as this
module is imported. Every entry point (app/config.py, app/main.py,
app/migrate.py, collectors/runner.py) imports this first, so
os.getenv() calls anywhere downstream -- including inside collector
__init__ methods and notifiers/telegram.py's module-level reads --
see values from .env without each of them calling load_dotenv() itself.

find_dotenv() walks up from the current working directory, so this
works whether you run commands from backend/ (as the README assumes)
or from a subdirectory.
"""
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
