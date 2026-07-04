import { Component, OnInit, OnDestroy,ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription, interval, forkJoin } from 'rxjs';
import { switchMap, map } from 'rxjs/operators';
import { ApiService, Analytics, ReviewRecord } from './services/api.service';



type StatusFilter = 'all' | 'approved' | 'blocked';
type SafetyFilter = 'all' | 'safe' | 'unsafe';
type SortColumn = 'pr_title' | 'score' | 'created_at';
type SortDirection = 'asc' | 'desc';

interface ChartPoint { x: number; y: number; score: number; }

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App implements OnInit, OnDestroy {

  analytics: Analytics | null = null;
  history: ReviewRecord[] = [];

  loading = true;
  error: string | null = null;
  lastUpdated: Date | null = null;


  private pollSub: Subscription | null = null;
  private readonly POLL_MS = 60000;

  searchTerm = '';
  statusFilter: StatusFilter = 'all';
  safetyFilter: SafetyFilter = 'all';
  sortColumn: SortColumn = 'created_at';
  sortDirection: SortDirection = 'desc';

  page = 1;
  readonly pageSize = 8;

  expandedRow: number | null = null;

  showClearConfirm = false;
  clearing = false;

  readonly CHART_W = 300;
  readonly CHART_H = 120;
  readonly PAD = { top: 12, right: 12, bottom: 12, left: 26 };

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) { }

  ngOnInit() { console.log('App component initialized'); this.startPolling(); }
  ngOnDestroy() { this.pollSub?.unsubscribe(); }

  private fetchOnce() {
    return this.api.getAnalytics().pipe(
      switchMap(analytics =>
        this.api.getHistory().pipe(
          map(history => ({
            analytics,
            history
          }))
        )
      )
    );
  }

  startPolling() {
    this.loading = true;

    this.fetchOnce().subscribe({
      next: ({ analytics, history }) => {
        this.loading = false;
        console.log('loading after update =', this.loading);
        this.analytics = analytics;
        this.history = history;

        this.error = null;
        this.lastUpdated = new Date();
        this.cdr.detectChanges();

        console.log('Dashboard loaded');
      },
      error: (err) => {
        console.error(err);
        this.loading = false;
        this.error = 'Could not reach the DevPilot API';
      }
    });
  }

  refreshNow() {
    this.fetchOnce().subscribe({
      next: ({ analytics, history }) => this.applyData(analytics, history),
      error: () => { this.error = 'Refresh failed — check the API connection.'; }
    });
  }


  private applyData(analytics: Analytics, history: any) {
    this.loading = false;
    this.analytics = analytics;
    this.history = history;
    this.error = null;
    this.lastUpdated = new Date();
  }

  confirmClear() { this.showClearConfirm = true; }
  cancelClear() { this.showClearConfirm = false; }

  clearHistory() {
    this.clearing = true;
    this.api.deleteAllHistory().subscribe({
      next: () => {
        this.history = [];
        this.analytics = null;
        this.clearing = false;
        this.showClearConfirm = false;
        this.refreshNow();
      },
      error: () => {
        this.clearing = false;
        this.error = 'Failed to clear history — please try again.';
      }
    });
  }

  setStatusFilter(f: StatusFilter) { this.statusFilter = f; this.page = 1; this.expandedRow = null; }
  setSafetyFilter(f: SafetyFilter) { this.safetyFilter = f; this.page = 1; this.expandedRow = null; }

  onSearchChange() { this.page = 1; this.expandedRow = null; }

  setSort(col: SortColumn) {
    if (this.sortColumn === col) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = col;
      this.sortDirection = col === 'pr_title' ? 'asc' : 'desc';
    }
    this.expandedRow = null;
  }

  sortIcon(col: SortColumn): string {
    if (this.sortColumn !== col) return '';
    return this.sortDirection === 'asc' ? '↑' : '↓';
  }

  private compareValues(a: ReviewRecord, b: ReviewRecord, col: SortColumn): number {
    if (col === 'score') {
      return (a.score ?? 0) - (b.score ?? 0);
    }
    const av = String(a[col] ?? '').toLowerCase();
    const bv = String(b[col] ?? '').toLowerCase();
    return av.localeCompare(bv);
  }

  get filteredHistory(): ReviewRecord[] {
    let rows = this.history;

    if (this.statusFilter === 'approved') rows = rows.filter(r => !r.blocked);
    if (this.statusFilter === 'blocked') rows = rows.filter(r => r.blocked);
    if (this.safetyFilter === 'safe') rows = rows.filter(r => r.is_safe);
    if (this.safetyFilter === 'unsafe') rows = rows.filter(r => !r.is_safe);

    const q = this.searchTerm.trim().toLowerCase();
    if (q) {
      rows = rows.filter(r =>
        r.pr_title?.toLowerCase().includes(q) ||
        r.filename?.toLowerCase().includes(q)
      );
    }

    const dir = this.sortDirection === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => this.compareValues(a, b, this.sortColumn) * dir);
  }

  get pagedHistory(): ReviewRecord[] {
    const start = (this.page - 1) * this.pageSize;
    return this.filteredHistory.slice(start, start + this.pageSize);
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.filteredHistory.length / this.pageSize));
  }

  prevPage() { if (this.page > 1) { this.page--; this.expandedRow = null; } }
  nextPage() { if (this.page < this.totalPages) { this.page++; this.expandedRow = null; } }

  toggleExpand(i: number) {
    this.expandedRow = this.expandedRow === i ? null : i;
  }

  get approvedPct(): number {
    const total = this.analytics?.total_reviews || 0;
    if (!total) return 0;
    const blocked = this.analytics?.blocked_prs || 0;
    return Math.round(((total - blocked) / total) * 100);
  }

  get safePct(): number {
    const total = this.analytics?.total_reviews || 0;
    if (!total) return 100;
    const unsafe = this.analytics?.security_issues || 0;
    return Math.round(((total - unsafe) / total) * 100);
  }

  get approvedGradient(): string {
    return `conic-gradient(var(--color-success) 0% ${this.approvedPct}%, var(--color-danger) ${this.approvedPct}% 100%)`;
  }

  get safeGradient(): string {
    return `conic-gradient(var(--color-success) 0% ${this.safePct}%, var(--color-danger) ${this.safePct}% 100%)`;
  }

  private get plotW(): number { return this.CHART_W - this.PAD.left - this.PAD.right; }
  private get plotH(): number { return this.CHART_H - this.PAD.top - this.PAD.bottom; }

  private scoreToY(score: number): number {
    const clamped = Math.min(Math.max(score, 0), 10);
    return this.PAD.top + (1 - clamped / 10) * this.plotH;
  }

  get scoreTrendPoints(): ChartPoint[] {
    const data = [...this.history].reverse();
    const n = data.length;
    if (n < 2) return [];
    const stepX = this.plotW / (n - 1);
    return data.map((r, i) => ({
      x: this.PAD.left + i * stepX,
      y: this.scoreToY(r.score ?? 0),
      score: r.score ?? 0
    }));
  }

  get scoreTrendPath(): string {
    const pts = this.scoreTrendPoints;
    if (!pts.length) return '';
    return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  }

  get scoreTrendAreaPath(): string {
    const pts = this.scoreTrendPoints;
    if (!pts.length) return '';
    const baseline = this.PAD.top + this.plotH;
    const first = pts[0];
    const last = pts[pts.length - 1];
    return `${this.scoreTrendPath} L${last.x.toFixed(1)},${baseline} L${first.x.toFixed(1)},${baseline} Z`;
  }

  get gridLines(): { score: number; y: number }[] {
    return [10, 5, 0].map(score => ({ score, y: this.scoreToY(score) }));
  }
}