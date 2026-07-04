import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface Analytics {
  total_reviews: number;
  blocked_prs: number;
  security_issues: number;
  average_score: number;
  approval_rate: number;
}

export interface Vulnerability {
  type: string;
  severity: string;
  line?: string;
  fix?: string;
}

export interface ReviewRecord {
  pr_title: string;
  pr_url: string;
  filename: string;
  score: number;
  is_safe: boolean;
  vulnerabilities: Vulnerability[];
  issues: string[];
  blocked: boolean;
  severity: string;
  summary: string;
  doc_summary: string;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private api = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getAnalytics(): Observable<Analytics> {
    return this.http.get<Analytics>(`${this.api}/api/analytics`);
  }

  getHistory(): Observable<ReviewRecord[]> {
    return this.http.get<ReviewRecord[]>(`${this.api}/api/history`);
  }

  /**
   * Permanently deletes every stored review.
   * The backend requires an explicit confirm=true query param as a safety check.
   */
  deleteAllHistory(): Observable<any> {
    return this.http.delete(`${this.api}/api/history`, { params: { confirm: 'true' } });
  }
}