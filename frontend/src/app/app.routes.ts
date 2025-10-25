import { Routes } from '@angular/router';
import { ChatComponent } from './chat/chat.component';
import { KnowledgeGraphComponent } from './knowledge-graph/knowledge-graph.component';

export const routes: Routes = [
	{ path: '', pathMatch: 'full', redirectTo: 'chat' },
	{ path: 'chat', component: ChatComponent },
	{ path: 'graph', component: KnowledgeGraphComponent },
	{ path: '**', redirectTo: 'chat' }
];
