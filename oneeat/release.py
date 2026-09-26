"""Taches post-deploiement executees une seule fois par release (hebergement sans SSH).

La CI ecrit le fichier RELEASE (sha du commit) dans l'archive deployee. Au premier
demarrage de Passenger avec une nouvelle release, on applique les migrations puis
on synchronise le catalogue de demo (idempotent, sans suppression). Un verrou evite
que plusieurs processus Passenger le fassent en parallele.
"""
import logging
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RELEASE_FILE = BASE_DIR / "RELEASE"
APPLIED_FILE = BASE_DIR / "tmp" / "release_applied"
LOCK_FILE = BASE_DIR / "tmp" / "release.lock"

logger = logging.getLogger("oneeat")


def apply_pending_release():
    try:
        release = RELEASE_FILE.read_text().strip()
    except OSError:
        return  # environnement local : rien a faire
    APPLIED_FILE.parent.mkdir(exist_ok=True)
    if APPLIED_FILE.exists() and APPLIED_FILE.read_text().strip() == release:
        return
    try:
        import fcntl
    except ImportError:  # Windows
        fcntl = None
    with open(LOCK_FILE, "w") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        if APPLIED_FILE.exists() and APPLIED_FILE.read_text().strip() == release:
            return
        import django
        from django.core.management import call_command
        django.setup()
        try:
            call_command("migrate", interactive=False, verbosity=0)
            call_command("sync_catalog", verbosity=0)
        except Exception:  # ne jamais bloquer le demarrage du site
            logger.exception("Echec des taches de release %s", release)
            return
        APPLIED_FILE.write_text(release)
        logger.info("Release %s appliquee (migrations + catalogue).", release)
    os.environ["ONEEAT_RELEASE"] = release
