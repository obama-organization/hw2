#!/usr/bin/python3
import configparser
import logging
import os
import re
import socket
import time
from contextlib import closing
from multiprocessing import Pool

import cv2
import pymysql
import requests

import substream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read(os.environ.get("SCAN_CONFIG", "/etc/rtsp-scan/config.ini"))

HOST_IP = socket.gethostbyname(socket.gethostname())
HOSTNAME = os.uname()[1]
SNAPSHOT_DIR = "/var/www/html/scan"
WORKERS = int(os.environ.get("SCAN_WORKERS", "20"))
UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def get_connection():
    return pymysql.connect(
        host=config["MySQL"]["host"],
        user=config["MySQL"]["user"],
        password=config["MySQL"]["password"],
        database=config["MySQL"]["database"],
    )


def select_link_list():
    with closing(get_connection()) as con, con.cursor() as cur:
        cur.execute("SELECT `path`, `login`, `passwd` FROM `view_support_path_default`")
        return cur.fetchall()


def select_ip_list():
    query = """SELECT `ip`, CONCAT(REPLACE(`ip`,'.','_'), '-', `country_code`, '-',
                      `region`, '-', `city`) AS name_camera
               FROM rtsp_scan WHERE `url` IS NULL AND `up` = %s"""
    with closing(get_connection()) as con, con.cursor() as cur:
        cur.execute(query, (HOSTNAME,))
        return cur.fetchall()


def insert_url(link_one, ip, link, login, passwd):
    query = """UPDATE `rtsp_scan`
               SET `url` = %s, `up` = %s, `link` = %s, `login` = %s, `passwd` = %s
               WHERE `ip` = %s"""
    with closing(get_connection()) as con, con.cursor() as cur:
        cur.execute(query, (link_one, HOSTNAME, link, login, passwd, ip))
        con.commit()
    log.info("Updated record for %s", ip)


def job(item):
    rtsp_url, ip, camera_name, login, passwd = item
    safe_name = UNSAFE_CHARS.sub("_", camera_name)
    cap = cv2.VideoCapture(rtsp_url)
    try:
        ret, frame = cap.read()
        if not ret:
            return
        cv2.imwrite(os.path.join(SNAPSHOT_DIR, f"{safe_name}.jpg"), frame)
        link = f"http://{HOST_IP}/scan/{safe_name}.jpg"
        insert_url(rtsp_url, ip, link, login, passwd)
    except (cv2.error, pymysql.MySQLError, OSError) as exc:
        log.warning("Failed to process %s: %s", ip, exc)
    finally:
        cap.release()


def notify(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("Telegram is not configured, notification skipped")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Failed to send notification: %s", type(exc).__name__)


def main():
    for path, login, passwd in select_link_list():
        tasks = [
            [path.replace("ip_for_replace", ip), ip, name, login, passwd]
            for ip, name in select_ip_list()
        ]
        start = time.time()
        with Pool(processes=WORKERS) as pool:
            pool.map(job, tasks)
        pause = 300 - int(time.time() - start)
        log.info("Cycle finished, sleeping %s s", max(pause, 0))
        if pause > 0:
            time.sleep(pause)


if __name__ == "__main__":
    started = time.time()
    main()
    notify(f"41_scan_stream_default done - {int(time.time() - started)}")
    substream.main()
