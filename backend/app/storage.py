from pathlib import Path
import httpx
from .config import settings


class Storage:
    def __init__(self):
        self.remote = bool(settings.supabase_url and settings.supabase_service_key)
        self.root = Path(settings.data_dir) / 'evidence'
        self.root.mkdir(exist_ok=True)

    def request(self, method, key, data=None):
        url = f'{settings.supabase_url.rstrip("/")}/storage/v1/object/{settings.evidence_bucket}/{key}'
        result = httpx.request(method, url, headers={'Authorization': f'Bearer {settings.supabase_service_key}',
            'apikey': settings.supabase_service_key, 'Content-Type': 'image/jpeg', 'x-upsert': 'true'}, content=data, timeout=15)
        if method == 'DELETE' and result.status_code == 404:
            return result
        result.raise_for_status()
        return result

    def put(self, key, data):
        if self.remote:
            self.request('POST', key, data)
        else:
            dest = self.root / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

    def get(self, key):
        return self.request('GET', key).content if self.remote else (self.root / key).read_bytes()

    def delete(self, key):
        if self.remote:
            self.request('DELETE', key)
        else:
            (self.root / key).unlink(missing_ok=True)


storage = Storage()
