import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Production (cPanel / Passenger) : pas de mode debug par defaut.
os.environ.setdefault("DJANGO_DEBUG", "0")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oneeat.settings")

from oneeat.release import apply_pending_release  # noqa: E402

apply_pending_release()

from oneeat.wsgi import application  # noqa: E402,F401
