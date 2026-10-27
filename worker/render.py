"""Senaryo -> video işçisi (GitHub Actions üzerinde çalışır).

Akış: Supabase'ten job al -> sahnelere böl -> her sahneyi paralel üret
(ses: edge-tts, görsel: Pollinations, altyazı: Pillow, klip: ffmpeg)
-> klipleri birleştir -> Supabase Storage'a yükle -> job'u güncelle.
"""
import asyncio
import os
import re
import subprocess
import sys
import textwrap
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import edge_tts
import requests
from PIL import Image, ImageDraw, ImageFont

JOB_ID = os.environ["JOB_ID"]
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

WIDTH, HEIGHT = 1280, 720
WORKERS = 3                       # aynı anda üretilen sahne sayısı
IMG_SLOTS = threading.Semaphore(2)  # Pollinations'a aynı anda en fazla 2 istek
MAX_UPLOAD_BYTES = 49 * 1024 * 1024  # Supabase ücretsiz: 50 MB
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def update(**fields):
    try:
        requests.patch(
            f"{URL}/rest/v1/jobs?id=eq.{JOB_ID}",
            headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json=fields,
            timeout=30,
        )
    except Exception as e:  # durum güncellemesi render'ı durdurmasın
        print("update hatası:", e)


def get_job():
    r = requests.get(f"{URL}/rest/v1/jobs?id=eq.{JOB_ID}&select=*", headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError("Job bulunamadı")
    return rows[0]


def chunk_text(text, limit=220):
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    out, cur = [], ""
    for s in sentences:
        if cur and len(cur) + 1 + len(s) > limit:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def split_scenes(script):
    scenes = []
    for line in script.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r"\[img:\s*(.*?)\]", line, re.I)
        prompt = m.group(1).strip() if m else None
        text = re.sub(r"\[img:.*?\]", "", line, flags=re.I).strip()
        if not text:
            continue
        for chunk in chunk_text(text):
            scenes.append({"text": chunk, "prompt": prompt or chunk})
    return scenes


def run(cmd):
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{cmd[0]} hatası: {(e.stderr or '')[-400:]}")


async def _tts(text, voice, path):
    await edge_tts.Communicate(text, voice).save(str(path))


def make_audio(text, voice, path):
    last = None
    for attempt in range(4):
        try:
            asyncio.run(_tts(text, voice, path))
            if path.exists() and path.stat().st_size > 1000:
                return
        except Exception as e:
            last = e
            print("tts yeniden deneniyor:", e)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Ses üretilemedi: {last}")


def fetch_image(prompt, seed, dest):
    q = urllib.parse.quote(("cinematic, detailed, " + prompt)[:300])
    url = f"https://image.pollinations.ai/prompt/{q}?width={WIDTH}&height={HEIGHT}&nologo=true&seed={seed}"
    for attempt in range(4):
        try:
            with IMG_SLOTS:
                r = requests.get(url, timeout=90)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                dest.write_bytes(r.content)
                Image.open(dest).verify()
                return True
            print("görsel yanıtı:", r.status_code)
        except Exception as e:
            print("görsel yeniden deneniyor:", e)
        time.sleep(6 * (attempt + 1))
    return False


def gradient():
    img = Image.new("RGB", (WIDTH, HEIGHT))
    d = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        d.line([(0, y), (WIDTH, y)], fill=(int(20 + 30 * t), int(30 + 20 * t), int(70 + 60 * t)))
    return img


def load_font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_frame(text, img_path, out):
    img = None
    if img_path and img_path.exists():
        try:
            img = Image.open(img_path).convert("RGB")
            ratio = max(WIDTH / img.width, HEIGHT / img.height)
            img = img.resize((int(img.width * ratio) + 1, int(img.height * ratio) + 1), Image.LANCZOS)
            left, top = (img.width - WIDTH) // 2, (img.height - HEIGHT) // 2
            img = img.crop((left, top, left + WIDTH, top + HEIGHT))
        except Exception:
            img = None
    if img is None:
        img = gradient()

    font = load_font(36)
    lines = textwrap.wrap(text, width=52)
    line_h = 48
    box_h = len(lines) * line_h + 40
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle((0, HEIGHT - box_h, WIDTH, HEIGHT), fill=(0, 0, 0, 170))
    y = HEIGHT - box_h + 20
    for ln in lines:
        d.text((WIDTH / 2, y), ln, font=font, fill=(255, 255, 255, 255), anchor="ma")
        y += line_h
    Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB").save(out)


def build_scene(i, sc, voice, work):
    audio = work / f"a{i}.mp3"
    raw = work / f"i{i}.jpg"
    frame = work / f"f{i}.png"
    part = work / f"s{i}.mp4"

    make_audio(sc["text"], voice, audio)
    got = fetch_image(sc["prompt"], i + 1, raw)
    make_frame(sc["text"], raw if got else None, frame)

    run([
        "ffmpeg", "-y", "-loop", "1", "-framerate", "25", "-i", str(frame),
        "-i", str(audio), "-af", "apad=pad_dur=0.5",
        "-c:v", "libx264", "-tune", "stillimage", "-crf", "30",
        "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "2",
        "-shortest", str(part),
    ])
    return part


def upload(path):
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise RuntimeError(
            f"Video {size // (1024 * 1024)} MB oldu, Supabase ücretsiz sınırı 50 MB. Senaryoyu kısalt."
        )
    with open(path, "rb") as f:
        r = requests.post(
            f"{URL}/storage/v1/object/videos/{JOB_ID}.mp4",
            headers={**HEADERS, "Content-Type": "video/mp4", "x-upsert": "true"},
            data=f,
            timeout=600,
        )
    if not r.ok:
        raise RuntimeError(f"Yükleme hatası {r.status_code}: {r.text[:300]}")
    return f"{URL}/storage/v1/object/public/videos/{JOB_ID}.mp4"


def main():
    try:
        job = get_job()
        update(status="rendering", progress=1)
        scenes = split_scenes(job["script"])
        if not scenes:
            raise RuntimeError("Senaryo boş")
        print(f"{len(scenes)} sahne")

        work = Path("work")
        work.mkdir(exist_ok=True)
        parts = [None] * len(scenes)
        done = 0

        ex = ThreadPoolExecutor(max_workers=WORKERS)
        try:
            futs = {ex.submit(build_scene, i, sc, job["voice"], work): i for i, sc in enumerate(scenes)}
            for fut in as_completed(futs):
                parts[futs[fut]] = fut.result()  # hata varsa burada fırlar
                done += 1
                update(progress=int(5 + 88 * done / len(scenes)))
        except BaseException:
            ex.shutdown(wait=False, cancel_futures=True)
            raise
        ex.shutdown(wait=True)

        listing = work / "list.txt"
        listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
        final = work / "final.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", "-movflags", "+faststart", str(final)])
        update(progress=96)

        public_url = upload(final)
        update(status="done", progress=100, video_url=public_url)
        print("Bitti:", public_url)
    except Exception as e:
        print("HATA:", e)
        update(status="error", error=str(e)[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
