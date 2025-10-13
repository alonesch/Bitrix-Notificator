import requests
import time
import json
import os
import threading
from PIL import Image, ImageDraw
import pystray
from win10toast_click import ToastNotifier
import webbrowser
import base64

#Ofuscado
def get_webhook_url():
   
    s = b'aHR0cHM6Ly92aWxsZWxhLmJpdHJpeDI0LmNvbS5ici9yZXN0LzI2ODQ4L2N0Y2Rwc2Qwd2o5aW8zN3cv'
    return base64.b64decode(s).decode()

# Configurações e sets de apontamento
WEBHOOK_URL = get_webhook_url()
CATEGORY_ID = 100
STAGE_ID_N2 = "C100:5"
SEEN_FILE = "seen_deals_n2.json"
LOG_FILE = "log_deals_n2.txt"
POLL_INTERVAL = 3  # timer scan

#Inicializador de notificações
toaster = ToastNotifier()
last_deal_url = None  # guarda o último link do chamado

#Funções

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(str(x) for x in json.load(f))
        except Exception:
            return set()
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False, indent=2)

def log_deal(deal, status):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {status} | ID {deal['ID']} | {deal.get('TITLE','Sem título')} | Etapa: {deal.get('STAGE_ID')}\n"
        f.write(line)

def fetch_batch(category_id=100, stage_id=None, start=0):
    url = f"{WEBHOOK_URL}crm.deal.list.json"
    payload = {
        "filter": {"CATEGORY_ID": category_id, "STAGE_ID": stage_id},
        "select": ["ID", "TITLE", "STAGE_ID", "DATE_CREATE"],
        "start": start
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise Exception(data.get("error_description") or data.get("error"))
    return data.get("result", [])

def fetch_all_deals(category_id=100, stage_id=None):
    all_deals = []
    start = 0
    while True:
        batch = fetch_batch(category_id, stage_id, start)
        if not batch:
            break
        all_deals.extend(batch)
        if len(batch) < 50:
            break
        start += len(batch)
    return all_deals

# Popup notifier
def notify_deal(deal, status):
    global last_deal_url
    last_deal_url = f"https://villela.bitrix24.com/crm/deal/details/{deal['ID']}/"

    title = "Alerta de Chamado"
    message = f"{status}\nID: {deal['ID']}\n{deal.get('TITLE','Sem título')}"

    try:
        # Notificação em thread separada (som removido)
        threading.Thread(target=lambda: toaster.show_toast(
            title=title,
            msg=message,
            icon_path=None,  
            duration=8,
            threaded=True
        )).start()
    except Exception as e:
        print("Erro ao notificar:", e)


def create_icon(color):
    width = 64
    height = 64
    image = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, height), fill=color)
    return image

def quit_action(icon, item):
    icon.stop()

def open_last_deal(icon, item):
    global last_deal_url
    if last_deal_url:
        webbrowser.open(last_deal_url)

#Função principal
def monitor_loop(icon):
    seen = load_seen()
    first_run = not bool(seen)
    
    while True:
        try:
            deals = fetch_all_deals(CATEGORY_ID, STAGE_ID_N2)
            current_ids = set(str(d['ID']) for d in deals)
            new_deals = []

            # Qualquer ID que esteja no N2 agora mas não estava antes é considerado novo ou retornado
            for d in deals:
                id_str = str(d['ID'])
                if id_str not in seen:
                    new_deals.append(d)

            # Remove IDs que saíram do N2
            seen.intersection_update(current_ids)

            # Adiciona novos/retornados e notifica
            for d in new_deals:
                id_str = str(d['ID'])
                status = "CHAMADO NOVO" if first_run == False and id_str not in seen else "CHAMADO VOLTOU"
                seen.add(id_str)
                log_deal(d, status)
                notify_deal(d, status)

            # Atualiza ícone da bandeja
            if new_deals:
                icon.icon = create_icon("green")
            else:
                icon.icon = create_icon("orange")
            
            icon.title = f"Chamados N2 Monitor: {len(deals)} no estágio N2"
            save_seen(seen)
            first_run = False

        except Exception as e:
            print("Erro ao buscar deals:", e)

        time.sleep(POLL_INTERVAL)

# Início do tray
def start_tray():
    icon = pystray.Icon("monitor_n2")
    icon.icon = create_icon("orange")
    icon.title = "Chamados N2 Monitor"
    icon.menu = pystray.Menu(
        pystray.MenuItem("Abrir último chamado no Bitrix", open_last_deal),
        pystray.MenuItem("Sair", lambda icon, item: quit_action(icon, item))
    )
    threading.Thread(target=monitor_loop, args=(icon,), daemon=True).start()
    icon.run()


if __name__ == "__main__":
    start_tray()
