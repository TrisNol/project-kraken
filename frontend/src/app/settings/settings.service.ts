import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  // Optionally override by setting (window as any).__API_URL__
  private readonly apiBase: string = 'http://localhost:8000';

  async ingest(): Promise<any> {
    const url = `${this.apiBase}/index/create`;
    const res = await fetch(url, { method: 'POST', headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error(`Ingest request failed with status ${res.status}`);
    try {
      return await res.json();
    } catch {
      return { status: 'ok' };
    }
  }

  async clear(): Promise<any> {
    const url = `${this.apiBase}/index/clear`;
    const res = await fetch(url, { method: 'POST', headers: { Accept: 'application/json' } });
    if (!res.ok) throw new Error(`Clear request failed with status ${res.status}`);
    try {
      return await res.json();
    } catch {
      return { status: 'ok' };
    }
  }
}
