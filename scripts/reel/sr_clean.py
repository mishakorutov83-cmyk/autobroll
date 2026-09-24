"""Careful AI clean-up of a low-res source range (deblock/denoise + upscale), no face restoration.

  <venv>/bin/python scripts/reel/sr_clean.py <src> <start> <dur> <out.mp4> <model> <W> <H> [denoise]

model: path to a spandrel-loadable model (e.g. 2xNomosUni_span_multijpg, realesr-general-x4v3).
For realesr-general the optional denoise (0..1) blends in the -wdn weights, as Real-ESRGAN's own CLI does.
Output: frames resized to W×H (the selects' cover size) with lanczos, 30 fps, audio from the source.
"""
import subprocess, sys, time
import numpy as np, torch, spandrel

src, start, dur, out, model_path, W, H = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5], int(sys.argv[6]), int(sys.argv[7])
denoise = float(sys.argv[8]) if len(sys.argv) > 8 else None
torch.set_num_threads(4)

desc = spandrel.ModelLoader().load_from_file(model_path)
if denoise is not None and "realesr-general-x4v3" in model_path:
    wdn = spandrel.ModelLoader().load_from_file(model_path.replace("x4v3", "wdn-x4v3"))
    sd, sdw = desc.model.state_dict(), wdn.model.state_dict()
    desc.model.load_state_dict({k: (1 - denoise) * sdw[k] + denoise * sd[k] for k in sd})
model = desc.model.eval()

probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().split(",")
w, h = int(probe[0]), int(probe[1])
dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", src, "-vf", "fps=30",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
s = desc.scale
enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w * s}x{h * s}", "-r", "30",
                        "-i", "-", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", src, "-map", "0:v", "-map", "1:a?",
                        "-vf", f"scale={W}:{H}:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "14", "-g", "30", "-c:a", "aac", "-b:a", "192k", "-shortest", out], stdin=subprocess.PIPE)
t0, n = time.time(), 0
with torch.inference_mode():
    while True:
        buf = dec.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        x = torch.from_numpy(np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()).permute(2, 0, 1)[None].float() / 255
        y = model(x).clamp(0, 1)[0].permute(1, 2, 0).mul(255).round().byte().numpy()
        enc.stdin.write(y.tobytes())
        n += 1
enc.stdin.close(); enc.wait()
print(f"{out}: {n} frames in {time.time() - t0:.0f}s")
