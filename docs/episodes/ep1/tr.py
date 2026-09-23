from faster_whisper import WhisperModel
import json
m = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
segs, info = m.transcribe("audio.wav", language="ru", word_timestamps=True, vad_filter=False, beam_size=5,
  initial_prompt="Интервью. Ведущий Михаил, гость Мовсар. Китай, бизнес, ресторан «Наше место».")
out=[]
for s in segs:
    out.append({"start":s.start,"end":s.end,"text":s.text,"words":[{"w":w.word,"s":w.start,"e":w.end,"p":w.probability} for w in s.words]})
    print(f"[{s.start:7.2f}-{s.end:7.2f}] {s.text}", flush=True)
json.dump(out, open("transcript.json","w"), ensure_ascii=False)
print("DONE")
