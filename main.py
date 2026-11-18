"""ZONE DE FRAPPE — point d'entrée.

Lancement :            python main.py
Fenêtré forcé :        python main.py --window 1600x900
Test automatique :     python main.py --autotest
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
os.chdir(HERE)


def main():
    parser = argparse.ArgumentParser(description="ZONE DE FRAPPE")
    parser.add_argument("--window", help="force une fenêtre de taille LxH, ex. 1600x900")
    parser.add_argument("--autotest", action="store_true", help="exécute la batterie de tests automatiques")
    parser.add_argument("--out", default=None, help="dossier de sortie des captures du test automatique")
    args = parser.parse_args()
    size = None
    if args.window:
        w, h = args.window.lower().split("x")
        size = (int(w), int(h))
    autopilot = None
    if args.autotest:
        import tempfile
        # profil et réglages isolés : le test ne touche jamais aux données du joueur
        os.environ["ZDF_CONFIG_DIR"] = tempfile.mkdtemp(prefix="zdf_test_")
        from tests.autotest import AutoPilot
        autopilot = AutoPilot(args.out)
        size = size or (1600, 900)
    from engine.app import App
    app = App(autopilot=autopilot, windowed_size=size)
    app.run()
    if autopilot is not None:
        sys.exit(autopilot.exit_code)


if __name__ == "__main__":
    main()
