import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const api = (import.meta as any).env.VITE_API_URL || 'http://localhost:8000';
const password = (import.meta as any).env.VITE_APP_PASSWORD || '';
const headers = { 'x-app-password': password };

type Plan = {
  day_type?: string;
  main_focus?: { topic?: string; score?: number };
  secondary_focus?: { topic?: string; score?: number } | null;
  training?: Record<string, string> | null;
  admin?: Record<string, string> | null;
  quiz?: { count?: number };
  avoid?: string[];
};

function App() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [facts, setFacts] = useState<any[]>([]);
  const [quiz, setQuiz] = useState<any[]>([]);
  const [error, setError] = useState<string>('');
  const d = new Date().toISOString().slice(0, 10);

  const get = (url: string) =>
    fetch(url, { headers }).then(async (response) => {
      if (!response.ok) throw new Error(`Request failed (${response.status}). Check password/env.`);
      return response.json();
    });

  const load = () =>
    get(`${api}/api/plan/today?date=${d}`)
      .then((data) => {
        setPlan(data);
        setError('');
      })
      .catch((err) => setError(String(err.message || err)));

  useEffect(() => {
    load();
    get(`${api}/api/facts?status=needs_review`).then(setFacts).catch(() => {});
    get(`${api}/api/quiz/today?date=${d}`).then(setQuiz).catch(() => {});
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1 className="title">Command Card</h1>
        <button
          className="btn"
          onClick={() =>
            fetch(`${api}/api/plan/generate?date=${d}`, { method: 'POST', headers }).then(() => load())
          }
        >
          Generate today&apos;s plan
        </button>
      </header>
      {error ? <p style={{ color: '#b91c1c' }}>{error}</p> : null}

      <div className="grid">
        <section className="card">
          <h2>Dashboard / Today</h2>
          <div className="kv">
            <strong>Day type</strong>
            <span className="badge">{plan?.day_type ?? 'Not generated'}</span>
            <strong>Main focus</strong>
            <span>{plan?.main_focus?.topic ?? '-'}</span>
            <strong>Secondary</strong>
            <span>{plan?.secondary_focus?.topic ?? '-'}</span>
            <strong>Training</strong>
            <span>{plan?.training?.hint ?? '-'}</span>
            <strong>Admin</strong>
            <span>{plan?.admin?.hint ?? '-'}</span>
            <strong>Quiz count</strong>
            <span>{plan?.quiz?.count ?? quiz.length}</span>
          </div>
          <p>
            <strong>Avoid:</strong>{' '}
            {plan?.avoid && plan.avoid.length > 0 ? plan.avoid.join(', ') : 'None'}
          </p>
        </section>

        <section className="card">
          <h2>Quiz</h2>
          <p>
            Selected today: <strong>{quiz.length}</strong>
          </p>
          {quiz[0] ? (
            <p>
              <strong>First prompt:</strong> {quiz[0].prompt}
            </p>
          ) : (
            <p>No quiz questions yet.</p>
          )}
        </section>

        <section className="card">
          <h2>Notes to Facts</h2>
          <p>
            Needs review: <strong>{facts.length}</strong>
          </p>
          <p>Only approved facts can generate quiz questions.</p>
        </section>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
