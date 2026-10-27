'use client';

import { useEffect, useRef, useState } from 'react';
import { MAX_CHARS, CHARS_PER_MIN } from '@/lib/limits';

const VOICES = [
  ['tr-TR-EmelNeural', 'Türkçe - Emel (kadın)'],
  ['tr-TR-AhmetNeural', 'Türkçe - Ahmet (erkek)'],
  ['it-IT-ElsaNeural', 'İtalyanca - Elsa (kadın)'],
  ['it-IT-IsabellaNeural', 'İtalyanca - Isabella (kadın)'],
  ['it-IT-DiegoNeural', 'İtalyanca - Diego (erkek)'],
  ['en-US-AriaNeural', 'İngilizce - Aria (kadın)'],
  ['en-US-GuyNeural', 'İngilizce - Guy (erkek)'],
];

const EXAMPLE = `Roma'da sabah erken saatlerde sokaklar sessizdir. [img: quiet Rome street at sunrise, cinematic]
Kahve kokusu fırınlardan yayılır ve şehir yavaş yavaş uyanır.
Bugün size bu şehirde günlük hayatta kullanacağınız beş cümleyi öğreteceğim.`;

const box = {
  width: '100%',
  boxSizing: 'border-box',
  background: '#1a1f36',
  color: '#e8eaf6',
  border: '1px solid #343b63',
  borderRadius: 10,
  padding: 12,
  fontSize: 16,
};

export default function Home() {
  const [script, setScript] = useState('');
  const [voice, setVoice] = useState(VOICES[0][0]);
  const [password, setPassword] = useState('');
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    const saved = localStorage.getItem('vs_password');
    if (saved) setPassword(saved);
    return () => clearInterval(timer.current);
  }, []);

  function poll(id) {
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      try {
        const r = await fetch(`/api/jobs/${id}`, { cache: 'no-store' });
        const d = await r.json();
        if (r.ok) {
          setJob(d);
          if (d.status === 'done' || d.status === 'error') {
            clearInterval(timer.current);
            setBusy(false);
          }
        }
      } catch {}
    }, 5000);
  }

  async function submit() {
    setError('');
    setJob(null);
    setBusy(true);
    try {
      localStorage.setItem('vs_password', password);
      const r = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script, voice, password }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || 'Hata');
      setJob({ id: d.id, status: 'queued', progress: 0 });
      poll(d.id);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  const len = script.length;
  const minutes = (len / CHARS_PER_MIN).toFixed(1);
  const tooLong = len > MAX_CHARS;
  const label = {
    queued: 'Sırada (GitHub başlatıyor, 30-60 sn)',
    rendering: 'Video üretiliyor (uzun videolar 10-25 dk sürebilir)',
    done: 'Hazır',
    error: 'Hata',
  };

  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: 16 }}>
      <h1 style={{ fontSize: 24 }}>Video Studio</h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>
        Her satır bir sahne olur. Görsel istersen satıra [img: ingilizce tarif] ekle.
      </p>

      <textarea
        style={{ ...box, minHeight: 260 }}
        value={script}
        onChange={(e) => setScript(e.target.value)}
        placeholder={EXAMPLE}
      />
      <p style={{ margin: '6px 0 0', fontSize: 14, color: tooLong ? '#ff8a8a' : '#9aa3d4' }}>
        {len} / {MAX_CHARS} karakter · tahmini süre ≈ {minutes} dk
      </p>

      <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
        <select style={box} value={voice} onChange={(e) => setVoice(e.target.value)}>
          {VOICES.map(([v, n]) => (
            <option key={v} value={v}>{n}</option>
          ))}
        </select>
        <input
          style={box}
          type="password"
          placeholder="Uygulama şifresi"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button
          onClick={submit}
          disabled={busy || tooLong || script.trim().length < 10}
          style={{ ...box, background: busy || tooLong ? '#343b63' : '#4f6bff', border: 'none', fontWeight: 700, cursor: 'pointer' }}
        >
          {busy ? 'Çalışıyor...' : 'Videoyu oluştur'}
        </button>
      </div>

      {error && <p style={{ color: '#ff8a8a' }}>{error}</p>}

      {job && (
        <section style={{ marginTop: 20 }}>
          <p>
            Durum: <b>{label[job.status] || job.status}</b>
            {job.status === 'rendering' ? ` (%${job.progress})` : ''}
          </p>
          {job.status === 'error' && <p style={{ color: '#ff8a8a' }}>{job.error}</p>}
          {job.status === 'done' && job.video_url && (
            <>
              <video src={job.video_url} controls style={{ width: '100%', borderRadius: 10 }} />
              <p>
                <a style={{ color: '#9db0ff' }} href={job.video_url} target="_blank" rel="noreferrer">
                  Videoyu aç (uzun bas ve kaydet / indir)
                </a>
              </p>
            </>
          )}
        </section>
      )}
    </main>
  );
}
