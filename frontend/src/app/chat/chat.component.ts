import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatService, ChatMessage } from './chat.service';
import { MarkdownComponent } from 'ngx-markdown';
import { MultiSelectModule } from 'primeng/multiselect';
import { PopoverModule } from 'primeng/popover';

@Component({
    selector: 'app-chat',
    templateUrl: './chat.component.html',
    styleUrls: ['./chat.component.scss'],
    imports: [FormsModule, MarkdownComponent, MultiSelectModule, PopoverModule],
    changeDetection: ChangeDetectionStrategy.OnPush
})
export class ChatComponent {
    private readonly chat = inject(ChatService);

    // UI state signals
    input = signal('');
    isThinking = signal(false);
    messages = signal<ChatMessage[]>([]);

    // Sources multi-select (settings)
    selectedSources: string[] = ['JIRA', 'CONFLUENCE', 'GITHUB'];
    sourceOptions = [
        { label: 'Jira', value: 'JIRA' },
        { label: 'Confluence', value: 'CONFLUENCE' },
        { label: 'GitHub', value: 'GITHUB' }
    ];

    // Auto-scroll effect on new messages
    constructor() {
        effect(() => {
            // access messages to create dependency
            this.messages();
            queueMicrotask(() => {
                const el = document.querySelector('.chat__messages');
                if (el) el.scrollTop = el.scrollHeight;
            });
        });
        
        // Load chat history on initialization
        this.loadChatHistory();
    }

    private async loadChatHistory() {
        try {
            const history = await this.chat.getChatHistory();
            if (history.length > 0) {
                this.messages.set(history);
            }
        } catch (err) {
            console.error('Failed to load chat history:', err);
        }
    }

    async clearHistory() {
        try {
            await this.chat.clearChatHistory();
            this.messages.set([]);
        } catch (err) {
            console.error('Failed to clear chat history:', err);
        }
    }

    // Note: Popover (OverlayPanel) is toggled from template using a template reference variable

    async send() {
        const text = this.input().trim();
        if (!text || this.isThinking()) return;

        const userMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'user',
            content: text,
            createdAt: new Date()
        };
        this.messages.update((arr) => [...arr, userMsg]);
        this.input.set('');

        this.isThinking.set(true);
        try {
            const ans = await this.chat.ask(text, this.selectedSources);
            const assistantMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: 'assistant',
                content: ans.content,
                refs: ans.refs,
                createdAt: new Date()
            };
            this.messages.update((arr) => [...arr, assistantMsg]);
        } finally {
            this.isThinking.set(false);
        }
    }
}
