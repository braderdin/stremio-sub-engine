#!/usr/bin/env python3
import os
import requests
from pathlib import Path

# Path ke fail .env.local
ENV_PATH = Path("/home/braderdin/stremio-sub-engine/.env.local")

def load_env(env_path):
    """Membaca fail .env.local secara manual."""
    env_vars = {}
    if not env_path.exists():
        print(f"❌ Fail {env_path} tidak dijumpai!")
        return env_vars

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()
    return env_vars

def flush_redis(redis_url, redis_token):
    print("\n🧹 Mengosongkan Upstash Redis DB...")
    if not redis_url or not redis_token:
        print("❌ Kunci UPSTASH_REDIS_REST_URL / TOKEN tidak ditemui dalam .env.local")
        return

    # Menghantar arahan FLUSHDB melalui REST API
    endpoint = f"{redis_url.rstrip('/')}/flushdb"
    headers = {"Authorization": f"Bearer {redis_token}"}

    try:
        res = requests.get(endpoint, headers=headers)
        if res.status_code == 200:
            print("✅ Upstash Redis berjaya dikosongkan (FLUSHDB)!")
        else:
            print(f"❌ Gagal membersihkan Redis: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Ralat semasa menghubungi Redis: {e}")

def flush_search(search_url, search_token):
    print("\n🧹 Mengosongkan Upstash Search / Vector DB...")
    if not search_url or not search_token:
        print("❌ Kunci UPSTASH_SEARCH_REST_URL / TOKEN tidak ditemui dalam .env.local")
        return

    # Menghantar arahan reset indeks melalui REST API
    endpoint = f"{search_url.rstrip('/')}/reset"
    headers = {"Authorization": f"Bearer {search_token}"}

    try:
        res = requests.post(endpoint, headers=headers)
        if res.status_code == 200:
            print("✅ Upstash Search DB berjaya dikosongkan (RESET)!")
        else:
            print(f"❌ Gagal membersihkan Search DB: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Ralat semasa menghubungi Search DB: {e}")

def main():
    print("🚀 Memulakan proses pembersihan data Upstash...")
    env_vars = load_env(ENV_PATH)

    redis_url = env_vars.get("UPSTASH_REDIS_REST_URL")
    redis_token = env_vars.get("UPSTASH_REDIS_REST_TOKEN")

    search_url = env_vars.get("UPSTASH_SEARCH_REST_URL")
    search_token = env_vars.get("UPSTASH_SEARCH_REST_TOKEN")

    flush_redis(redis_url, redis_token)
    flush_search(search_url, search_token)
    
    print("\n✨ Semua data telah dipadam. Sedia untuk projek baru!")

if __name__ == "__main__":
    main()