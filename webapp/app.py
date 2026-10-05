"""Bangla handwriting IoT: phone photo -> CNN -> MQTT -> ESP32.
Run:  python app.py      then open  http://<laptop-ip>:5000  on your phone (same WiFi/hotspot)."""
import os, io, json, base64, tempfile
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np, cv2, keras
from flask import Flask, request, jsonify, render_template_string
from preprocess_bangla import preprocess

CHARS = "অ আ ই ঈ উ ঊ ঋ এ ঐ ও ঔ ক খ গ ঘ ঙ চ ছ জ ঝ ঞ ট ঠ ড ঢ ণ ত থ দ ধ ন প ফ ব ভ ম য র ল শ ষ স হ ড় ঢ় য় ৎ ং ঃ ঁ".split()
DEMO = "ক খ গ জ ত দ ল র ও ঃ".split()          # closed set for the demo, edit freely (or set DEMO = CHARS)
DEMO_IDX = [CHARS.index(c) for c in DEMO]
MIN_CONF, MIN_MARGIN = 0.60, 0.25                # below this -> "retake photo"
MQTT_HOST, MQTT_TOPIC = os.getenv("MQTT_HOST", "localhost"), "bangla/result"

model = keras.models.load_model(os.path.join(os.path.dirname(__file__), "bangla_cnn_model_final.keras"), compile=False)

mqtt = None
try:
    import paho.mqtt.client as paho
    mqtt = paho.Client(paho.CallbackAPIVersion.VERSION2) if hasattr(paho, "CallbackAPIVersion") else paho.Client()
    mqtt.connect(MQTT_HOST, 1883, 30); mqtt.loop_start()
except Exception as e:
    print("MQTT not connected (running without ESP32):", e); mqtt = None

app = Flask(__name__)

def classify(path):
    img64 = preprocess(path)                                   # 64x64, white on black, raw 0..255 (NO /255)
    p = model.predict(img64.astype("float32")[None, :, :, None], verbose=0)[0]
    sub = p[DEMO_IDX]; sub = sub / sub.sum()                   # only compare letters in the demo set
    order = np.argsort(sub)[::-1]
    top = [{"char": DEMO[i], "idx": DEMO_IDX[i], "conf": round(float(sub[i]) * 100, 1)} for i in order[:3]]
    in_set = int(np.argmax(p)) in DEMO_IDX                      # full 50-class winner must be a demo letter, else reject
    ok = bool(in_set and sub[order[0]] >= MIN_CONF and sub[order[0]] - sub[order[1]] >= MIN_MARGIN)
    return img64, top, ok

@app.post("/predict")
def predict():
    f = request.files["photo"]
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as t:
        f.save(t.name)
    try:
        img64, top, ok = classify(t.name)
    except Exception:
        return jsonify(error="Letter not found in photo, try again with a clearer shot"), 422
    finally:
        os.unlink(t.name)
    msg = {"idx": top[0]["idx"], "conf": top[0]["conf"], "ok": ok}
    if mqtt: mqtt.publish(MQTT_TOPIC, json.dumps(msg))
    png = base64.b64encode(cv2.imencode(".png", img64)[1]).decode()
    return jsonify(top=top, ok=ok, preview=png, sent=bool(mqtt))

PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>Bangla Handwriting AI</title>
<body style="font-family:system-ui,'Noto Sans Bengali',sans-serif;max-width:420px;margin:auto;padding:16px;text-align:center">
<h2>Bangla Handwriting AI</h2>
<input id=f type=file accept="image/*" capture=environment style="margin:12px">
<div id=out></div>
<script>
f.onchange = async () => {
  out.innerHTML = "Predicting...";
  const fd = new FormData(); fd.append("photo", f.files[0]);
  const r = await fetch("/predict", {method:"POST", body:fd}); const d = await r.json();
  if (d.error) { out.innerHTML = "<p style='color:#c00'>"+d.error+"</p>"; return; }
  const t = d.top[0];
  out.innerHTML = `<div style="font-size:96px;line-height:1.2">${t.char}</div>
   <div>Confidence: ${t.conf}%</div>
   <p style="font-weight:600;color:${d.ok?'#080':'#c60'}">${d.ok?'Accepted':'Not sure, retake the photo'}</p>
   <img src="data:image/png;base64,${d.preview}" width=128 style="image-rendering:pixelated;border:1px solid #888"><br>
   <small>what the model saw</small><br>
   <small>Others: ${d.top.slice(1).map(x=>x.char+' '+x.conf+'%').join(', ')}</small><br>
   <small>ESP32: ${d.sent?'sent':'not connected'}</small>`;
};
</script>"""

@app.get("/")
def home(): return render_template_string(PAGE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
