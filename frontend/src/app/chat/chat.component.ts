import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatService, ChatMessage } from './chat.service';
import { MarkdownComponent } from 'ngx-markdown';

@Component({
    selector: 'app-chat',
    templateUrl: './chat.component.html',
    styleUrls: ['./chat.component.scss'],
    imports: [FormsModule, MarkdownComponent],
    changeDetection: ChangeDetectionStrategy.OnPush
})
export class ChatComponent {
    private readonly chat = inject(ChatService);

    // UI state signals
    input = signal('');
    isThinking = signal(false);
    messages = signal<ChatMessage[]>([]);

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
    }

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
            const ans = await this.chat.ask(text);
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
