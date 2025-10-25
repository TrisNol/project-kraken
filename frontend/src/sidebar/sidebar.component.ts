import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
	selector: 'app-sidebar',
		imports: [RouterLink, RouterLinkActive],
	templateUrl: './sidebar.component.html',
	styleUrl: './sidebar.component.scss',
	host: {
		'[class.collapsed]': 'collapsed'
	}
})
export class SidebarComponent {
	collapsed = false;

	toggleCollapse() {
		this.collapsed = !this.collapsed;
	}
}
