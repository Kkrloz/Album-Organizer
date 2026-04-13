#!/usr/bin/env python3
"""
Criado por: Carlos Eduardo G. Ribeiro
Github: @Kkrloz

album_organizer.py - Versão 4.0 (A Escolha do Colecionador / Prioridade Local)
Organiza coleções musicais respeitando os dados originais das pastas locais.

Destaques desta versão:
- Confia no Ano e Nome do Álbum definidos nas pastas locais do utilizador.
- Usa as APIs (Internet) APENAS para descarregar a Capa e buscar Anos em falta.
- Limpeza de faixas duplicadas (resolve o problema "01. 01 Nome da Música").
- Compatível com Python 3.14.
"""

import os
import re
import sys
import time
import shutil
import argparse
import urllib.request
import urllib.parse
import urllib.error
import json

try:
    from mutagen import File as MutagenFile
    from mutagen.easyid3 import EasyID3
except ImportError:
    print("Erro: mutagen não está instalado. Execute: pip install mutagen")
    sys.exit(1)

# Configurações e APIs
AUDIO_EXTENSIONS = {".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wav", ".wv", ".ape"}
MUSICBRAINZ_API  = "https://musicbrainz.org/ws/2"
COVER_ART_API    = "https://coverartarchive.org/release"
ITUNES_API       = "https://itunes.apple.com/search"
DEEZER_API       = "https://api.deezer.com/search/album"
USER_AGENT       = "AlbumOrganizer/4.0 (Script de Colecionador)"

LOCAL_COVER_NAMES = ["folder.jpg", "folder.png", "front.jpg", "front.png",
                     "cover.png", "albumart.jpg", "albumart.png", "thumb.jpg"]

# ── helpers ───────────────────────────────────────────────────────────────────

def log(msg, level="info"):
    icons = {"info": "·", "ok": "✓", "skip": "–", "warn": "!", "err": "✗"}
    print(f"  {icons.get(level, '·')} {msg}")

def audio_files(folder):
    return sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
    )

def safe_filename(name):
    """Remove caracteres inválidos em nomes de ficheiro/pasta."""
    if not name: return ""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return re.sub(r' {2,}', ' ', name).strip()

def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

def http_download(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
    with open(dest_path, "wb") as f:
        f.write(data)

# ── tags e metadados ──────────────────────────────────────────────────────────

def read_track_tags(filepath):
    """Lê as tags atuais ID3. Retorna (track_num, title)."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        audio = EasyID3(filepath) if ext == ".mp3" else MutagenFile(filepath, easy=True)
        if audio is None: return None, None
        
        title = str(audio.get("title", [""])[0]).strip() or None
        track_num = None
        val = audio.get("tracknumber")
        if val:
            raw = str(val[0]).split("/")[0].strip()
            if raw.isdigit(): track_num = int(raw)
        return track_num, title
    except Exception:
        return None, None

def save_tags(filepath, artist, album, year, track_num, title):
    """Grava fisicamente as tags no ficheiro de áudio."""
    try:
        audio = MutagenFile(filepath, easy=True)
        if audio is None: return False
        if audio.tags is None:
            try: audio.add_tags()
            except: pass

        if artist: audio['artist'] = [artist]
        if album:  audio['album']  = [album]
        if year:   audio['date']   = [str(year)]
        if title:  audio['title']  = [title]
        if track_num is not None: audio['tracknumber'] = [str(track_num)]

        audio.save()
        return True
    except Exception as e:
        log(f"Falha ao gravar tags em {os.path.basename(filepath)}: {e}", "warn")
        return False

def parse_filename_fallback(filename, artist_name=""):
    """Extrai info do nome do ficheiro se as tags estiverem vazias."""
    base = os.path.splitext(filename)[0]
    match = re.match(r'^(\d+)\s*[-.]*\s*(.+)$', base)
    if match:
        track_num, title = int(match.group(1)), match.group(2).strip()
    else:
        track_num, title = None, base.strip()

    if artist_name:
        pattern = re.compile(r'[-\s_]*\b(?:by\s+)?' + re.escape(artist_name) + r'\b.*$', re.IGNORECASE)
        title = re.sub(pattern, '', title)

    title = re.sub(r'\s+(19|20)\d{2}.*$', '', title)
    return track_num, title.strip(' -_()[]')

def extract_local_metadata(folder_name, artist_name=""):
    """Extrai o Ano e o Nome do Álbum diretamente da pasta do utilizador."""
    name = folder_name
    year = None
    
    # Busca um ano válido (19xx ou 20xx) em qualquer parte do nome
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
    if year_match:
        year = year_match.group(1)
        
    # Remove o nome do artista para limpar (mas APENAS se o álbum não for homônimo)
    if artist_name and name.lower().replace(" ", "") != artist_name.lower().replace(" ", ""):
        name = re.sub(rf'^{re.escape(artist_name)}\s*[-_]*\s*', '', name, flags=re.IGNORECASE)
        
    # Remove o ano para deixar o título limpo (agora prevê parênteses no início também!)
    name = re.sub(r'^[\(\[]?((19|20)\d{2})[\)\]]?\s*[-.]*\s*', '', name)
    name = re.sub(r'\s*[\(\[]?((19|20)\d{2})[\)\]]?$', '', name)
    
    name = name.strip()
    
    # Se por acaso a limpeza apagou tudo, devolve o nome original como fallback de segurança
    if not name:
        name = folder_name
        
    return year, name

# ── busca de dados (Internet) ─────────────────────────────────────────────────

def fetch_metadata_from_apis(artist, album):
    """Busca APENAS dados complementares (MBID da capa e Ano se faltar)."""
    # MusicBrainz
    try:
        time.sleep(1.1)
        query = urllib.parse.quote(f'release:"{album}" AND artist:"{artist}"')
        data = http_get_json(f"{MUSICBRAINZ_API}/release?query={query}&limit=5&fmt=json")
        if data.get("releases"):
            best = max(data["releases"], key=lambda r: int(r.get("score", 0)))
            date = best.get("date", "")
            year = date[:4] if len(date) >= 4 else None
            return year, best.get("id")
    except: pass

    # iTunes
    try:
        params = urllib.parse.urlencode({"term": f"{artist} {album}", "media": "music", "entity": "album"})
        data = http_get_json(f"{ITUNES_API}?{params}")
        if data.get("results"):
            best = data["results"][0]
            date = best.get("releaseDate", "")
            year = date[:4] if len(date) >= 4 else None
            return year, None
    except: pass

    return None, None

def fetch_cover(artist, album, album_path, mbid, overwrite):
    dest = os.path.join(album_path, "cover.jpg")
    if os.path.exists(dest) and not overwrite: return

    success = False
    if mbid:
        try:
            http_download(f"{COVER_ART_API}/{mbid}/front-500", dest)
            success = True
        except: pass
    
    if not success:
        try:
            params = urllib.parse.urlencode({"term": f"{artist} {album}", "entity": "album"})
            data = http_get_json(f"{ITUNES_API}?{params}")
            url = data["results"][0]["artworkUrl100"].replace("100x100bb", "600x600bb")
            http_download(url, dest)
            success = True
        except: pass

    if success: log(f"cover.jpg salva", "ok")

# ── formatação e organização ──────────────────────────────────────────────────

def format_album_folder(final_album_name, year):
    """Gera o nome da pasta no formato 'Álbum (Ano)'."""
    name = safe_filename(final_album_name)
    if year and f"({year})" not in name:
        name = f"{name} ({year})"
    return name

def process_and_tag_tracks(album_path, artist, final_album_name, year, dry_run):
    for fname in sorted(os.listdir(album_path)):
        fpath = os.path.join(album_path, fname)
        ext = os.path.splitext(fname)[1].lower()
        if not os.path.isfile(fpath) or ext not in AUDIO_EXTENSIONS: continue

        track_num, title = read_track_tags(fpath)
        if not title or track_num is None:
            t_fb, n_fb = parse_filename_fallback(fname, artist)
            track_num = track_num if track_num is not None else t_fb
            title = title or n_fb

        if not title: title = "Faixa desconhecida"

        # LIMPEZA DE NÚMEROS DUPLICADOS (A "Mágica" para o caso do Led Zeppelin)
        # Se a tag do título começar com o número da faixa (ex: "01 In The Evening"), cortamos o número.
        if track_num is not None:
            title = re.sub(rf'^0*{track_num}\s*[-.]*\s+', '', title).strip()

        if not dry_run:
            save_tags(fpath, artist, final_album_name, year, track_num, title)

        new_name = f"{int(track_num or 0):02d}. {safe_filename(title)}{ext}"
        if new_name != fname:
            new_path = os.path.join(album_path, new_name)
            if not os.path.exists(new_path):
                if not dry_run: os.rename(fpath, new_path)
                log(f"'{fname}' → '{new_name}'", "ok")

def process_library(root, args):
    if not os.path.isdir(root): sys.exit("Erro: Caminho inválido.")

    total_albums = 0

    for artist in sorted(os.listdir(root)):
        artist_path = os.path.join(root, artist)
        if not os.path.isdir(artist_path): continue

        for album in sorted(os.listdir(artist_path)):
            album_path = os.path.join(artist_path, album)
            if not os.path.isdir(album_path) or not audio_files(album_path): continue

            total_albums += 1
            print(f"\n[{artist}] {album}")
            
            # 1. Extração de Metadados da Pasta (Curadoria do Colecionador)
            local_year, clean_album_local = extract_local_metadata(album, artist)
            
            # 2. Busca Complementar na Internet
            log("buscando capa e dados complementares...")
            api_year, mbid = fetch_metadata_from_apis(artist, clean_album_local)
            
            # 3. Consolidação (Prioridade Total aos dados Locais)
            final_year = local_year if local_year else api_year
            final_album_name = clean_album_local

            log(f"Álbum: '{final_album_name}'", "ok")
            if final_year:
                origem = "Local" if local_year else "Internet"
                log(f"Ano: {final_year} ({origem})", "ok")
            
            # 4. Processa e embute tags limpas
            process_and_tag_tracks(album_path, artist, final_album_name, final_year, args.dry_run)

            # 5. Renomeia a pasta com o padrão
            new_folder_name = format_album_folder(final_album_name, final_year)
            new_path = os.path.join(artist_path, new_folder_name)
            
            if not args.dry_run and album_path != new_path and not os.path.exists(new_path):
                os.rename(album_path, new_path)
                album_path = new_path
                log(f"Pasta: → {new_folder_name}", "ok")

            # 6. Capa e M3U
            if not args.dry_run:
                if not args.only_m3u: fetch_cover(artist, final_album_name, album_path, mbid, args.overwrite)
                if not args.only_cover:
                    with open(os.path.join(album_path, f"{new_folder_name}.m3u"), "w", encoding="utf-8") as f:
                        f.write("#EXTM3U\n" + "\n".join(audio_files(album_path)))
                    log("M3U criado", "ok")

    print(f"\n{'─'*50}")
    print(f"  álbuns processados : {total_albums}")
    if args.dry_run:
        print(f"  dry-run ativo      : nada foi alterado")
    print()

def main():
    parser = argparse.ArgumentParser(description="Organizador de Álbuns v4.0")
    parser.add_argument("root", help="Pasta Raiz (contém os artistas)")
    parser.add_argument("--dry-run", action="store_true", help="Não altera ficheiros")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescreve capas/m3u")
    parser.add_argument("--only-cover", action="store_true")
    parser.add_argument("--only-m3u", action="store_true")
    args = parser.parse_args()
    
    print(f"\nAlbum Organizer 4.0 (Prioridade Local)")
    print(f"{'─'*50}")
    
    process_library(args.root, args)

if __name__ == "__main__": main()
