"""Flask — จอผู้ใช้จริงที่ /  และแดชบอร์ดเดโมที่ /dev"""
from flask import Flask, Response, jsonify, render_template, request

import core

app = Flask(__name__)
S = core.Session()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/dev")
def dev():
    return render_template("dev.html", cams=core.list_cams(), models=core.MODELS)


@app.get("/state")
def state():
    return jsonify(S.state())


@app.post("/toggle")
def toggle():
    S.stop() if S.running else S.start()
    return jsonify(S.state())


@app.post("/config")
def config():
    d = request.get_json(force=True)
    if "cam" in d and int(d["cam"]) != S.cam:
        S.cam = int(d["cam"])
        core.save_cam(S.cam)
        if S.running:                         # เปลี่ยนกล้องต้องเปิดใหม่
            S.stop(); S.start()
    for k in ("every", "model", "mirror", "still", "scene", "alert", "fast_on"):
        if k in d:
            setattr(S, k, d[k])
            S.auto = False                    # ตั้งเองแล้ว เลิก auto
    if d.get("recalibrate"):
        S.auto = True
        if S.running:
            S.stop(); S.start()
    if d.get("forget"):
        S.recent, S.summary, S.narrative = [], "", ""
    return jsonify(S.state())


@app.get("/video")
def video():
    dev_view = request.args.get("dev") == "1"

    def gen():
        import time
        while True:
            jpg = S.jpeg(dev_view)
            if jpg:
                yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.03)                  # ~30fps เพดานกล้องอยู่แล้ว
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=f")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, threaded=True, debug=False)
