import { Routes } from '@angular/router';
import { ChatComponent } from './chat/chat.component';
import { KnowledgeGraphComponent } from './knowledge-graph/knowledge-graph.component';
import { HeroComponent } from './hero/hero.component';
import { SettingsComponent } from './settings/settings.component';

export const routes: Routes = [
	{ path: '', component: HeroComponent },
	{ path: 'chat', component: ChatComponent },
	{ path: 'graph', component: KnowledgeGraphComponent },
	{ path: 'settings', component: SettingsComponent },
	{ path: '**', redirectTo: 'chat' }
];
