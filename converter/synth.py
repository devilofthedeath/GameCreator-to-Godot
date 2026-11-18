import os, math, struct, wave

def sng_bytes_to_wav(sng_data: bytes, out_wav_path: str, sample_rate: int = 22050):
    # Каждый байт в .sng — это шаг трекера (~0.06 сек). 0xFF = пауза, остальные — высота ноты
    step_samples = int(sample_rate * 0.06)
    pcm = bytearray()

    for b in sng_data:
        if b == 255 or b == 0:
            pcm.extend(b"\x80" * step_samples)
        else:
            # Переводим байт трекера в частоту (Гц) в диапазоне 110..1760 Гц
            midi_note = 36 + (b % 60)
            freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
            period = max(2, int(sample_rate / freq))
            half = period // 2
            # Генерируем чистый 8-битный меандр (square wave) с затуханием
            for i in range(step_samples):
                val = 165 if (i % period) < half else 90
                pcm.append(val)

    with wave.open(out_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(1)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(pcm))
