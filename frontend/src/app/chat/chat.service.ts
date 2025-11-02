import { Injectable } from '@angular/core';

export type ChatRole = 'user' | 'assistant';

export interface ChatReference {
  title: string;
  url: string;
  /**
   * Legacy/simple icon hint used for CSS fallbacks. Prefer `iconUrl` when available.
   */
  icon?: 'link' | 'doc' | 'code';
  /**
   * Optional URL to an icon image served by the API (e.g. `/icon?type=JIRA`).
   * When present the UI should render the image.
   */
  iconUrl?: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  refs?: ChatReference[];
  createdAt: Date;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  // Optionally allow overriding the API base URL by setting (window as any).__API_URL__ = 'http://localhost:8000'
  private readonly apiBase: string = 'http://localhost:8000';

  async ask(prompt: string): Promise<Omit<ChatMessage, 'id' | 'role' | 'createdAt'>> {
    const url = `${this.apiBase}/ask?question=${encodeURIComponent(prompt)}`;

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }

      type DocumentSourceType = 'JIRA' | 'CONFLUENCE' | 'GITHUB';
      interface BaseMetadata {
        source?: string;
        type: DocumentSourceType;
        last_updated?: string;
        // Specific fields by type (optional since union is not enforced at runtime)
        issue_key?: string; // JIRA
        project_key?: string; // JIRA
        page_id?: string; // Confluence
        space_key?: string; // Confluence
        repo_name?: string; // GitHub
        file_path?: string; // GitHub
        commit_hash?: string; // GitHub
        ref?: string; // GitHub
      }
      interface ResponseModel {
        answer: string;
        source_documents: BaseMetadata[];
      }

      const data = (await res.json()) as ResponseModel;

      const refs: ChatReference[] = (data.source_documents ?? []).map((doc): ChatReference => {
        const icon: ChatReference['icon'] = doc.type === 'GITHUB' ? 'code' : doc.type === 'CONFLUENCE' ? 'doc' : 'link';
        // Build a URL for the backend icon endpoint so the UI can render an image.
        const iconUrl = `${this.apiBase}/icon?type=${encodeURIComponent(doc.type)}`;

        // Prefer backend-provided link in `source`, otherwise try to construct a sensible fallback
        let url = doc.source || '';
        if (!url && doc.type === 'GITHUB' && doc.repo_name && doc.file_path) {
          const ref = doc.ref || 'main';
          url = `https://github.com/${doc.repo_name}/blob/${encodeURIComponent(ref)}/${doc.file_path}`;
        }
        const title =
          doc.type === 'JIRA' && doc.issue_key
            ? `Jira ${doc.issue_key}`
            : doc.type === 'CONFLUENCE' && (doc.page_id || doc.space_key)
            ? `Confluence ${doc.page_id ?? doc.space_key}`
            : doc.type === 'GITHUB' && (doc.repo_name || doc.file_path)
            ? `GitHub ${doc.repo_name ?? ''}${doc.file_path ? `/${doc.file_path}` : ''}`.trim()
            : doc.type;
        return { title, url: url || '#', icon, iconUrl };
      });

      return { content: data.answer, refs };
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      return {
        content: `Sorry, I couldn't get an answer from the server. ${message}`,
        refs: []
      };
    }
  }
}
