#!/usr/bin/env python3
"""Démarre Gestion Scolaire pour TOUS les appareils du réseau Wi-Fi.

    python lancer_reseau.py            # compile l'interface si besoin, puis démarre
    python lancer_reseau.py --port 8080
    python lancer_reseau.py --recompiler   # force la compilation de l'interface
    python lancer_reseau.py --sans-build   # n'essaie pas de compiler

Les téléphones, tablettes et autres ordinateurs connectés au même Wi-Fi ouvrent
ensuite l'adresse affichée (http://192.168.x.x:8000). Rien à installer sur eux.
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
BACKEND = RACINE / 'backend'
FRONTEND = RACINE / 'frontend'
BUILD = FRONTEND / 'build'
EXTENSIONS_SOURCES = {'.js', '.jsx', '.css', '.json', '.html', '.svg', '.png', '.ico'}


def adresse_locale():
    """Adresse IP de ce PC sur le réseau (aucun paquet n'est réellement envoyé)."""
    sonde = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sonde.connect(('10.255.255.255', 1))
        return sonde.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        sonde.close()


def build_a_jour(build=BUILD, sources=(FRONTEND / 'src', FRONTEND / 'public', FRONTEND / 'package.json')):
    """True si l'interface compilée existe et est plus récente que ses sources."""
    index = Path(build) / 'index.html'
    if not index.is_file():
        return False
    reference = index.stat().st_mtime
    for source in sources:
        source = Path(source)
        fichiers = [source] if source.is_file() else (
            p for p in source.rglob('*') if p.is_file() and p.suffix in EXTENSIONS_SOURCES)
        if any(f.stat().st_mtime > reference for f in fichiers):
            return False
    return True


def executer(commande, dossier, env=None):
    # sous Windows, npm est un script (npm.cmd) : il faut passer par le shell
    return subprocess.run(commande, cwd=dossier, env=env, shell=(os.name == 'nt')).returncode == 0


def compiler_interface():
    if shutil.which('npm') is None:
        print("! Node.js / npm est introuvable : impossible de compiler l'interface.")
        print("  Installez Node.js (https://nodejs.org) ou compilez sur un autre PC puis copiez frontend/build.")
        return False
    if not (FRONTEND / 'node_modules').is_dir():
        print('> Installation des dépendances de l\'interface (npm install)…')
        if not executer(['npm', 'install'], FRONTEND):
            return False
    print("> Compilation de l'interface (npm run build)…")
    env = dict(os.environ, CI='false')   # les simples avertissements ne doivent pas bloquer
    return executer(['npm', 'run', 'build'], FRONTEND, env)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--recompiler', action='store_true', help="force la compilation de l'interface")
    parser.add_argument('--sans-build', action='store_true', help="ne tente pas de compiler l'interface")
    args = parser.parse_args()

    if not args.sans_build and (args.recompiler or not build_a_jour()):
        if not compiler_interface() and not (BUILD / 'index.html').is_file():
            print("\nL'interface n'est pas disponible : le serveur démarre quand même (API seule).")

    ip = adresse_locale()
    print('\n' + '=' * 62)
    print('  Gestion Scolaire — accessible sur le réseau local')
    print('=' * 62)
    print(f'  Sur ce PC              : http://localhost:{args.port}')
    print(f'  Autres appareils (Wi-Fi): http://{ip}:{args.port}')
    print('=' * 62)
    print('  Si les autres appareils n\'arrivent pas à se connecter, autorisez')
    print(f'  Python dans le pare-feu Windows (réseau privé) / le port {args.port}.')
    print('  Arrêt : Ctrl + C\n')

    env = dict(os.environ, RESEAU_LOCAL='1')
    try:
        subprocess.run([sys.executable, 'manage.py', 'runserver', f'0.0.0.0:{args.port}'],
                       cwd=BACKEND, env=env)
    except KeyboardInterrupt:
        print('\nServeur arrêté.')


if __name__ == '__main__':
    main()
