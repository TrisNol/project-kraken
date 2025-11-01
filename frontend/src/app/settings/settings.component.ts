import { Component, signal, inject } from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { SettingsService } from './settings.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss'],
  imports: [ButtonModule]
})
export class SettingsComponent {
  private readonly settings = inject(SettingsService);

  isWorking = signal(false);
  message = signal('');

  async ingest() {
    if (this.isWorking()) return;
    this.isWorking.set(true);
    this.message.set('Ingesting documents...');
    try {
      const res = await this.settings.ingest();
      this.message.set(JSON.stringify(res));
    } catch (err) {
      this.message.set(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      this.isWorking.set(false);
    }
  }

  async clear() {
    if (this.isWorking()) return;
    this.isWorking.set(true);
    this.message.set('Clearing index...');
    try {
      const res = await this.settings.clear();
      this.message.set(JSON.stringify(res));
    } catch (err) {
      this.message.set(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      this.isWorking.set(false);
    }
  }
}
