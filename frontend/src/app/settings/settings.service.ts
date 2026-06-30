import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  // Optionally override by setting (window as any).__API_URL__
  private readonly apiBase: string = 'http://localhost:8000';

  async getConfig(): Promise<any> {
    const url = `${this.apiBase}/config`;
    const res = await fetch(url, { 
      method: 'GET', 
      headers: { Accept: 'application/json' },
      credentials: 'include'
    });
    if (!res.ok) throw new Error(`Config request failed with status ${res.status}`);
    return await res.json();
  }

  async ingest(): Promise<any> {
    const url = `${this.apiBase}/index/create`;
    const res = await fetch(url, { 
      method: 'POST', 
      headers: { Accept: 'application/json' },
      credentials: 'include'
    });
    if (!res.ok) throw new Error(`Ingest request failed with status ${res.status}`);
    try {
      return await res.json();
    } catch {
      return { status: 'ok' };
    }
  }

  async clear(): Promise<any> {
    const url = `${this.apiBase}/index/clear`;
    const res = await fetch(url, { 
      method: 'POST', 
      headers: { Accept: 'application/json' },
      credentials: 'include'
    });
    if (!res.ok) throw new Error(`Clear request failed with status ${res.status}`);
    try {
      return await res.json();
    } catch {
      return { status: 'ok' };
    }
  }
}
