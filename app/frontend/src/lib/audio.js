// Reliable mic recorder: captures raw PCM straight from the getUserMedia stream
// via Web Audio (no MediaRecorder / decodeAudioData, which fails on some
// webm/opus builds) and returns a 16 kHz mono 16-bit WAV — the format Sarvam
// STT expects.
export function createRecorder() {
  let ctx = null;
  let source = null;
  let processor = null;
  let stream = null;
  let buffers = [];
  let inRate = 48000;
  let level = 0; // instantaneous level for a live meter (0..1)
  let peak = 0; // overall peak across the recording

  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const AC = window.AudioContext || window.webkitAudioContext;
      ctx = new AC();
      if (ctx.state === "suspended") await ctx.resume();
      inRate = ctx.sampleRate;
      source = ctx.createMediaStreamSource(stream);
      processor = ctx.createScriptProcessor(4096, 1, 1);
      buffers = [];
      peak = 0;
      processor.onaudioprocess = (e) => {
        const data = e.inputBuffer.getChannelData(0);
        buffers.push(new Float32Array(data));
        let m = 0;
        for (let i = 0; i < data.length; i += 8) {
          const a = Math.abs(data[i]);
          if (a > m) m = a;
        }
        level = m;
        if (m > peak) peak = m;
      };
      source.connect(processor);
      processor.connect(ctx.destination);
    },
    getLevel() {
      return level;
    },
    async stop() {
      try {
        processor && processor.disconnect();
        source && source.disconnect();
      } catch { /* ignore */ }
      stream && stream.getTracks().forEach((t) => t.stop());

      let total = 0;
      buffers.forEach((b) => (total += b.length));
      const merged = new Float32Array(total);
      let off = 0;
      buffers.forEach((b) => { merged.set(b, off); off += b.length; });

      const out = resampleLinear(merged, inRate, 16000);
      try { ctx && (await ctx.close()); } catch { /* ignore */ }
      return { blob: encodeWav(out, 16000), peak, samples: total };
    },
  };
}

function resampleLinear(samples, inRate, outRate) {
  if (inRate === outRate) return samples;
  const ratio = inRate / outRate;
  const outLen = Math.floor(samples.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const idx = i * ratio;
    const i0 = Math.floor(idx);
    const i1 = Math.min(i0 + 1, samples.length - 1);
    out[i] = samples[i0] + (samples[i1] - samples[i0]) * (idx - i0);
  }
  return out;
}

// Convert a recorded audio Blob (webm/opus from MediaRecorder) into a
// 16 kHz mono 16-bit PCM WAV Blob — kept as a fallback path.
export async function blobToWav(blob, targetRate = 16000) {
  const arrayBuf = await blob.arrayBuffer();
  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC();
  const decoded = await ctx.decodeAudioData(arrayBuf);
  ctx.close?.();

  // Downmix to mono
  const chans = decoded.numberOfChannels;
  const len = decoded.length;
  const mono = new Float32Array(len);
  for (let c = 0; c < chans; c++) {
    const data = decoded.getChannelData(c);
    for (let i = 0; i < len; i++) mono[i] += data[i] / chans;
  }

  // Resample to targetRate (linear interpolation)
  const ratio = decoded.sampleRate / targetRate;
  const outLen = Math.floor(len / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const idx = i * ratio;
    const i0 = Math.floor(idx);
    const i1 = Math.min(i0 + 1, len - 1);
    out[i] = mono[i0] + (mono[i1] - mono[i0]) * (idx - i0);
  }

  return encodeWav(out, targetRate);
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (off, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}
