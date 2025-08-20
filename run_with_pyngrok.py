# run_with_pyngrok.py
from __future__ import annotations
import os, sys, time, socket, signal, subprocess
from contextlib import closing
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8501"))
NGROK_TOKEN = os.getenv("NGROK_AUTHTOKEN")
NGROK_REGION = os.getenv("NGROK_REGION", "eu")  # eu, us, ap, au, sa, jp, in

def wait_port(host: str, port: int, timeout: float = 30.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.settimeout(1.0)
            try:
                if s.connect_ex((host, port)) == 0:
                    return True
            except Exception:
                pass
        time.sleep(0.5)
    return False

def main():
    # 1) Streamlit’i başlat
    cmd = [
        sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
        "--server.port", str(PORT),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    streamlit_proc = subprocess.Popen(cmd)
    print(f"[run] Streamlit başlatıldı (port {PORT}), PID={streamlit_proc.pid}. Bekleniyor...")

    if not wait_port("127.0.0.1", PORT, timeout=45.0):
        print("[err] Streamlit porte bağlanılamadı. Loglara bakın.")
        streamlit_proc.terminate()
        sys.exit(1)

    # 2) pyngrok tünelini aç
    try:
        from pyngrok import ngrok, conf
    except Exception as e:
        print("[err] pyngrok bulunamadı. `pip install pyngrok`")
        streamlit_proc.terminate()
        sys.exit(1)

    if NGROK_TOKEN:
        conf.get_default().auth_token = NGROK_TOKEN
    conf.get_default().region = NGROK_REGION

    # Eski tünelleri kapat
    try:
        ngrok.kill()
    except Exception:
        pass

    print("[run] ngrok tüneli açılıyor...")
    tunnel = ngrok.connect(addr=PORT, proto="http", bind_tls=True)
    public_url = tunnel.public_url  # çoğunlukla http döner
    https_url = public_url.replace("http://", "https://")
    print("\n" + "="*70)
    print(f"  ✅ Kamuya açık URL: {https_url}")
    print("  (Tarayıcıya bu linki yapıştırın)")
    print("="*70 + "\n")

    # 3) Ctrl+C bekleyip temiz kapat
    try:
        streamlit_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ngrok.disconnect(public_url)
            ngrok.kill()
        except Exception:
            pass
        try:
            if streamlit_proc.poll() is None:
                # Windows uyumlu sonlandır
                if os.name == "nt":
                    streamlit_proc.send_signal(signal.CTRL_BREAK_EVENT)
                streamlit_proc.terminate()
        except Exception:
            pass
        print("[run] Kapatıldı.")

if __name__ == "__main__":
    main()
