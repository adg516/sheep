import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const env = (import.meta as any).env;
const defaultApi = env.VITE_API_URL || 'https://arjunsheep-api.fly.dev';
const defaultPassword = env.VITE_APP_PASSWORD || '';
const frontendHosts = ['arjunsheep.vercel.app'];

type Tab = 'Today' | 'Quiz' | 'Tasks' | 'Targets' | 'Notes' | 'Settings';
type Grade = 'again' | 'hard' | 'good' | 'easy';
type TaskStatus = 'planned' | 'done' | 'missed' | 'skipped';

type Topic = {
  id: number;
  name: string;
  category: string;
  priority_weight: number;
  active: boolean;
};

type WeeklyTarget = {
  id: number;
  topic_id: number;
  target_type: string;
  target_value: number;
  current_period_start: string;
  active: boolean;
};

type Task = {
  id: number;
  topic_id?: number | null;
  title: string;
  description?: string | null;
  energy_cost: string;
  duration_minutes: number;
  status: TaskStatus;
  scheduled_date?: string | null;
  completed_at?: string | null;
  created_at?: string;
};

type Source = {
  id: number;
  topic_id: number;
  title: string;
  source_type: string;
  raw_text: string;
  source_ref?: string | null;
};

type Choice = {
  label: string;
  text: string;
};

type Fact = {
  id: number;
  source_id: number;
  topic_id: number;
  fact_text: string;
  explanation: string;
  tags: string[];
  status: 'needs_review' | 'approved' | 'rejected';
};

type Question = {
  id: number;
  fact_id: number;
  topic_id: number;
  question_type?: string;
  prompt: string;
  correct_answer: string;
  acceptable_answers: string[];
  distractors?: string[] | null;
  choices?: Choice[];
  correct_choice?: string | null;
  metadata_json?: Record<string, any>;
  explanation: string;
  active: boolean;
};

type Plan = {
  id?: number;
  date?: string;
  day_type?: string;
  main_focus?: { topic?: string; score?: number; minutes?: number; suggestion?: string | null };
  secondary_focus?: { topic?: string; score?: number; minutes?: number; suggestion?: string | null } | null;
  training?: { hint?: string } | null;
  admin?: { hint?: string; options?: string[] } | null;
  quiz?: { count?: number };
  avoid?: string[];
};

type DdiaChapterSettings = {
  chapters: number[];
  available_chapters: number[];
};

type CheckIn = {
  id?: number;
  date: string;
  sleep_quality: 'bad' | 'meh' | 'good';
  soreness: 'low' | 'medium' | 'high';
  work_pressure: 'low' | 'medium' | 'high';
  notes?: string | null;
};

type CalendarEvent = {
  id: number;
  title: string;
  start_at: string;
  end_at: string;
  source: string;
  tags: string[];
};

type SetupState = {
  sleep_quality: CheckIn['sleep_quality'];
  soreness: CheckIn['soreness'];
  work_pressure: CheckIn['work_pressure'];
  training: 'none' | 'bjj' | 'lifting' | 'both' | 'other';
};

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
};

const tabs: Tab[] = ['Today', 'Quiz', 'Tasks', 'Targets', 'Notes', 'Settings'];
const categoryOrder = [
  { key: 'professional', title: 'Professional' },
  { key: 'language', title: 'Study' },
  { key: 'training', title: 'Training' },
  { key: 'admin', title: 'Admin' },
  { key: 'creative', title: 'Creative' },
  { key: 'social', title: 'Social' },
  { key: 'health', title: 'Health' },
  { key: 'other', title: 'Other' },
];

function localDateString(date = new Date()) {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 10);
}

function weekStart(dateString: string) {
  const date = new Date(`${dateString}T00:00:00`);
  const day = date.getDay() || 7;
  date.setDate(date.getDate() - day + 1);
  return localDateString(date);
}

function formatDate(dateString: string) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  }).format(new Date(`${dateString}T12:00:00`));
}

function titleCase(value?: string) {
  if (!value) return 'Not set';
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function displayCategory(value?: string) {
  if (!value) return 'Unmapped';
  if (value === 'language') return 'Study';
  return titleCase(value);
}

function getChoices(question?: Question): Choice[] {
  if (!question) return [];
  if (question.choices?.length) return question.choices;
  if (question.distractors?.length) {
    return [question.correct_answer, ...question.distractors].map((text, index) => ({
      label: String.fromCharCode(65 + index),
      text,
    }));
  }
  return [];
}

function normalizedAnswer(value: string) {
  return value.trim().toLowerCase();
}

function isAnswerCorrect(question: Question, userAnswer: string) {
  const normalized = normalizedAnswer(userAnswer);
  if (!normalized) return null;

  const choices = getChoices(question);
  const selectedChoice = choices.find(
    (choice) =>
      normalizedAnswer(choice.label) === normalized ||
      normalizedAnswer(choice.text) === normalized ||
      normalizedAnswer(`${choice.label}. ${choice.text}`) === normalized,
  );

  if (question.correct_choice && selectedChoice) {
    return normalizedAnswer(selectedChoice.label) === normalizedAnswer(question.correct_choice);
  }

  if (question.correct_choice && normalized === normalizedAnswer(question.correct_choice)) return true;
  const accepted = [question.correct_answer, ...(question.acceptable_answers || [])].map(normalizedAnswer);
  return accepted.includes(normalized);
}

function formatRange(
  start: unknown,
  end: unknown,
  singleLabel: string,
  rangeLabel: string,
) {
  const startNumber = Number(start);
  if (!Number.isFinite(startNumber)) return '';
  const endNumber = Number(end);
  if (Number.isFinite(endNumber) && endNumber !== startNumber) {
    return `${rangeLabel} ${startNumber}-${endNumber}`;
  }
  return `${singleLabel} ${startNumber}`;
}

function getSourceCitation(question?: Question) {
  const metadata = question?.metadata_json || {};
  const source = String(metadata.short_source || metadata.source_title || metadata.source || '').trim();
  const sourceName = source.includes('Data-Intensive') ? 'DDIA2' : source;
  const details = [];

  if (metadata.chapter !== undefined && metadata.chapter !== null) details.push(`Ch. ${metadata.chapter}`);
  if (metadata.section) details.push(String(metadata.section));

  const bookPages = formatRange(
    metadata.source_page_start ?? metadata.page_start,
    metadata.source_page_end ?? metadata.page_end,
    'p.',
    'pp.',
  );
  const pdfPages = formatRange(
    metadata.source_pdf_page_start ?? metadata.pdf_page_start,
    metadata.source_pdf_page_end ?? metadata.pdf_page_end,
    'PDF p.',
    'PDF pp.',
  );
  if (bookPages) details.push(bookPages);
  if (pdfPages) details.push(`(${pdfPages})`);

  if (!sourceName && !details.length) return '';
  return sourceName ? `${sourceName}: ${details.join(', ')}` : details.join(', ');
}

function isFrontendApiUrl(value: string) {
  const trimmed = value.trim().replace(/\/$/, '');
  if (!trimmed || trimmed.startsWith('/')) return true;
  try {
    const parsed = new URL(trimmed);
    return (
      parsed.origin === window.location.origin ||
      frontendHosts.includes(parsed.hostname) ||
      parsed.hostname.endsWith('-megabird87-1408s-projects.vercel.app')
    );
  } catch {
    return true;
  }
}

function storedApiBase() {
  const stored = localStorage.getItem('command-card-api-url') || '';
  if (stored && isFrontendApiUrl(stored)) {
    localStorage.removeItem('command-card-api-url');
    return defaultApi;
  }
  return stored || defaultApi;
}

function Button({ variant = 'secondary', size = 'md', className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`button button-${variant} button-${size} ${className}`.trim()}
      {...props}
    />
  );
}

function Card({
  children,
  className = '',
  tone = 'default',
}: {
  children: React.ReactNode;
  className?: string;
  tone?: 'default' | 'hero' | 'muted';
}) {
  return <section className={`card card-${tone} ${className}`.trim()}>{children}</section>;
}

function Badge({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode;
  tone?: 'neutral' | 'good' | 'warning' | 'danger' | 'accent';
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function ProgressBar({ value, label }: { value: number; label?: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="progress-wrap" aria-label={label}>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${clamped}%` }} />
      </div>
      {label ? <span className="progress-label">{label}</span> : null}
    </div>
  );
}

function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="segmented">
      {options.map((option) => (
        <button
          key={option.value}
          className={option.value === value ? 'segment active' : 'segment'}
          type="button"
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

function SectionHeader({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string;
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="section-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
      </div>
      {action ? <div className="section-action">{action}</div> : null}
    </div>
  );
}

function App() {
  const today = useMemo(() => localDateString(), []);
  const [activeTab, setActiveTab] = useState<Tab>('Today');
  const [apiBase, setApiBase] = useState(
    () => storedApiBase(),
  );
  const [appPassword, setAppPassword] = useState(
    () => localStorage.getItem('command-card-password') || defaultPassword,
  );
  const [settingsDraft, setSettingsDraft] = useState({ apiBase, appPassword });

  const [plan, setPlan] = useState<Plan | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [targets, setTargets] = useState<WeeklyTarget[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [approvedFacts, setApprovedFacts] = useState<Fact[]>([]);
  const [quiz, setQuiz] = useState<Question[]>([]);
  const [checkin, setCheckin] = useState<CheckIn | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [ddiaSettings, setDdiaSettings] = useState<DdiaChapterSettings>({
    chapters: [],
    available_chapters: [],
  });
  const [selectedDdiaChapters, setSelectedDdiaChapters] = useState<number[]>([]);

  const [setup, setSetup] = useState<SetupState>({
    sleep_quality: 'meh',
    soreness: 'medium',
    work_pressure: 'medium',
    training: 'none',
  });
  const [workTaskTitle, setWorkTaskTitle] = useState('');
  const [adminTaskTitle, setAdminTaskTitle] = useState('');
  const [noteTopicId, setNoteTopicId] = useState<number | ''>('');
  const [noteTitle, setNoteTitle] = useState('');
  const [noteText, setNoteText] = useState('');
  const [quizIndex, setQuizIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [answerRevealed, setAnswerRevealed] = useState(false);
  const [quizFeedback, setQuizFeedback] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const topicById = useMemo(() => new Map(topics.map((topic) => [topic.id, topic])), [topics]);
  const sourceById = useMemo(() => new Map(sources.map((source) => [source.id, source])), [sources]);
  const factById = useMemo(() => new Map([...facts, ...approvedFacts].map((fact) => [fact.id, fact])), [facts, approvedFacts]);

  const plannedToday = tasks.filter((task) => task.scheduled_date === today && task.status === 'planned');
  const adminTopic = topics.find((topic) => topic.name.toLowerCase() === 'admin');
  const mainTopic = topics.find(
    (topic) => topic.name.toLowerCase() === plan?.main_focus?.topic?.toLowerCase(),
  );
  const mainActionTask =
    plannedToday.find((task) => mainTopic && task.topic_id === mainTopic.id) ||
    plannedToday.find((task) => task.description === 'work_task') ||
    null;

  async function requestJson<T>(path: string, options: RequestInit & { body?: unknown } = {}) {
    const base = apiBase.replace(/\/$/, '');
    const url = `${base}${path.startsWith('/') ? path : `/${path}`}`;
    const body =
      options.body && typeof options.body !== 'string'
        ? JSON.stringify(options.body)
        : (options.body as BodyInit | null | undefined);
    const response = await fetch(url, {
      ...options,
      body,
      headers: {
        'Content-Type': 'application/json',
        'x-app-password': appPassword,
        ...(options.headers || {}),
      },
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => '');
      throw new Error(detail || `Request failed (${response.status})`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      const detail = await response.text().catch(() => '');
      if (detail.trim().startsWith('<!doctype') || detail.trim().startsWith('<html')) {
        localStorage.removeItem('command-card-api-url');
        setApiBase(defaultApi);
        setSettingsDraft((current) => ({ ...current, apiBase: defaultApi }));
        throw new Error('The saved API URL pointed at the frontend. I reset it to the production backend; refresh once if this stays visible.');
      }
      throw new Error(`Expected JSON from API but got ${contentType || 'a non-JSON response'}.`);
    }

    return response.json() as Promise<T>;
  }

  async function loadData() {
    if (!appPassword) {
      setError('Set the app password in Settings to connect to the local API.');
      return;
    }

    setLoading(true);
    try {
      const [
        nextPlan,
        nextCheckin,
        nextQuiz,
        nextTopics,
        nextTargets,
        nextTasks,
        nextSources,
        nextFacts,
        nextApprovedFacts,
        nextEvents,
        nextDdiaSettings,
      ] = await Promise.all([
        requestJson<Plan | null>(`/api/plan/today?date=${today}`),
        requestJson<CheckIn | null>(`/api/checkin?date=${today}`),
        requestJson<Question[]>(`/api/quiz/today?date=${today}`),
        requestJson<Topic[]>('/api/topics'),
        requestJson<WeeklyTarget[]>('/api/weekly-targets'),
        requestJson<Task[]>('/api/tasks'),
        requestJson<Source[]>('/api/sources'),
        requestJson<Fact[]>('/api/facts?status=needs_review'),
        requestJson<Fact[]>('/api/facts?status=approved'),
        requestJson<CalendarEvent[]>(`/api/calendar/events?date=${today}`),
        requestJson<DdiaChapterSettings>('/api/settings/ddia-chapters'),
      ]);

      setPlan(nextPlan);
      setCheckin(nextCheckin);
      setQuiz(nextQuiz);
      setTopics(nextTopics);
      setTargets(nextTargets);
      setTasks(nextTasks);
      setSources(nextSources);
      setFacts(nextFacts);
      setApprovedFacts(nextApprovedFacts);
      setEvents(nextEvents);
      setDdiaSettings(nextDdiaSettings);
      setSelectedDdiaChapters(nextDdiaSettings.chapters || []);
      setError('');
      if (quizIndex >= nextQuiz.length) setQuizIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [apiBase, appPassword]);

  useEffect(() => {
    if (!checkin) return;
    setSetup((current) => ({
      ...current,
      sleep_quality: checkin.sleep_quality,
      soreness: checkin.soreness,
      work_pressure: checkin.work_pressure,
    }));
  }, [checkin?.id]);

  useEffect(() => {
    const titles = events.map((event) => event.title.toLowerCase()).join(' ');
    if (titles.includes('bjj') && titles.includes('lifting')) {
      setSetup((current) => ({ ...current, training: 'both' }));
    } else if (titles.includes('bjj')) {
      setSetup((current) => ({ ...current, training: 'bjj' }));
    } else if (titles.includes('lifting')) {
      setSetup((current) => ({ ...current, training: 'lifting' }));
    } else if (titles.includes('train')) {
      setSetup((current) => ({ ...current, training: 'other' }));
    }
  }, [events.length]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (activeTab !== 'Quiz' || !answerRevealed) return;
      const grades: Grade[] = ['again', 'hard', 'good', 'easy'];
      const index = Number(event.key) - 1;
      if (index >= 0 && index < grades.length) {
        event.preventDefault();
        gradeQuestion(grades[index]);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [activeTab, answerRevealed, quizIndex, answer, quiz.length]);

  function topicName(topicId?: number | null) {
    return topicId ? topicById.get(topicId)?.name || 'Unmapped' : 'Work';
  }

  function topicCategory(task: Task) {
    return task.topic_id ? topicById.get(task.topic_id)?.category || 'other' : 'work';
  }

  function taskIsAdmin(task: Task) {
    return task.description === 'admin_task' || topicCategory(task) === 'admin';
  }

  function taskIsTraining(task: Task) {
    return topicCategory(task) === 'training';
  }

  function taskIsWork(task: Task) {
    return task.description === 'work_task' || topicCategory(task) === 'professional' || (!task.topic_id && !taskIsAdmin(task));
  }

  function toggleDdiaChapter(chapter: number) {
    setSelectedDdiaChapters((current) =>
      current.includes(chapter)
        ? current.filter((item) => item !== chapter)
        : [...current, chapter].sort((a, b) => a - b),
    );
  }

  async function saveDdiaChapters(chapters = selectedDdiaChapters) {
    setSaving(true);
    try {
      const next = await requestJson<DdiaChapterSettings>('/api/settings/ddia-chapters', {
        method: 'PATCH',
        body: { chapters },
      });
      setDdiaSettings(next);
      setSelectedDdiaChapters(next.chapters || []);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function generatePlan() {
    setSaving(true);
    try {
      const nextPlan = await requestJson<Plan>(`/api/plan/generate?date=${today}`, { method: 'POST' });
      setPlan(nextPlan);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function saveDailySetup() {
    setSaving(true);
    try {
      await requestJson<CheckIn>('/api/checkin', {
        method: 'POST',
        body: {
          date: today,
          sleep_quality: setup.sleep_quality,
          soreness: setup.soreness,
          work_pressure: setup.work_pressure,
        },
      });

      const trainingTitle = {
        none: '',
        bjj: 'BJJ',
        lifting: 'Lifting',
        both: 'BJJ + Lifting',
        other: 'Training',
      }[setup.training];

      if (trainingTitle) {
        const normalized = trainingTitle.toLowerCase();
        const alreadyExists = events.some((event) => event.title.toLowerCase() === normalized);
        if (!alreadyExists) {
          const late = setup.training === 'bjj' || setup.training === 'both';
          await requestJson<CalendarEvent>('/api/calendar/events/manual', {
            method: 'POST',
            body: {
              title: trainingTitle,
              start_at: `${today}T${late ? '20:30:00' : '18:00:00'}`,
              end_at: `${today}T${late ? '22:00:00' : '19:00:00'}`,
              source: 'manual',
              tags: ['training'],
            },
          });
        }
      }

      await generatePlan();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function addWorkTask() {
    const title = workTaskTitle.trim();
    if (!title) return;

    setSaving(true);
    try {
      await requestJson<Task>('/api/tasks', {
        method: 'POST',
        body: {
          title,
          description: 'work_task',
          energy_cost: 'medium',
          duration_minutes: 45,
          status: 'planned',
          scheduled_date: today,
        },
      });
      setWorkTaskTitle('');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function addAdminTask(titleOverride?: string) {
    const title = (titleOverride || adminTaskTitle).trim();
    if (!title) return;

    setSaving(true);
    try {
      await requestJson<Task>('/api/tasks', {
        method: 'POST',
        body: {
          title,
          description: 'admin_task',
          topic_id: adminTopic?.id,
          energy_cost: 'low',
          duration_minutes: 20,
          status: 'planned',
          scheduled_date: today,
        },
      });
      setAdminTaskTitle('');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function updateTaskStatus(task: Task, status: TaskStatus) {
    setSaving(true);
    try {
      if (status === 'done') {
        await requestJson<Task>(`/api/tasks/${task.id}/complete`, { method: 'POST' });
      } else if (status === 'missed') {
        await requestJson<Task>(`/api/tasks/${task.id}/miss`, { method: 'POST' });
      } else {
        await requestJson<Task>(`/api/tasks/${task.id}`, { method: 'PATCH', body: { status } });
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function markMainFocus(status: TaskStatus) {
    if (!plan?.main_focus?.topic) return;
    setSaving(true);
    try {
      if (mainActionTask) {
        await updateTaskStatus(mainActionTask, status);
        return;
      }

      await requestJson<Task>('/api/tasks', {
        method: 'POST',
        body: {
          title: `${plan.main_focus.topic} focus block`,
          topic_id: mainTopic?.id,
          energy_cost: 'medium',
          duration_minutes: 45,
          status,
          scheduled_date: today,
          completed_at: status === 'done' ? new Date().toISOString() : null,
        },
      });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  function revealAnswer() {
    if (!quiz[quizIndex]) return;
    setAnswerRevealed(true);
  }

  async function gradeQuestion(grade: Grade) {
    const question = quiz[quizIndex];
    if (!question) return;
    const inferredCorrect = isAnswerCorrect(question, answer);

    setSaving(true);
    try {
      const result = await requestJson<{ llm_feedback?: { feedback?: string } }>('/api/quiz/review', {
        method: 'POST',
        body: {
          question_id: question.id,
          user_answer: answer,
          grade,
          is_correct: inferredCorrect ?? (grade === 'good' || grade === 'easy'),
        },
      });
      setQuizFeedback(result.llm_feedback?.feedback || '');
      moveToNextQuestion();
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  function moveToNextQuestion() {
    setAnswer('');
    setAnswerRevealed(false);
    setQuizFeedback('');
    setQuizIndex((current) => Math.min(current + 1, quiz.length));
  }

  async function extractFacts() {
    const topicId = Number(noteTopicId || topics[0]?.id);
    if (!topicId || !noteText.trim()) return;

    setSaving(true);
    try {
      const source = await requestJson<Source>('/api/sources', {
        method: 'POST',
        body: {
          topic_id: topicId,
          title: noteTitle.trim() || 'Untitled source note',
          source_type: 'note',
          raw_text: noteText.trim(),
        },
      });
      await requestJson<Fact[]>(`/api/sources/${source.id}/extract-facts`, { method: 'POST' });
      setNoteTitle('');
      setNoteText('');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function patchFact(fact: Fact, patch: Partial<Fact>) {
    setSaving(true);
    try {
      await requestJson<Fact>(`/api/facts/${fact.id}`, { method: 'PATCH', body: patch });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function reviewFact(fact: Fact, action: 'approve' | 'reject') {
    setSaving(true);
    try {
      await requestJson<Fact>(`/api/facts/${fact.id}/${action}`, { method: 'POST' });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function generateQuestions(fact: Fact) {
    setSaving(true);
    try {
      await requestJson<Question[]>(`/api/facts/${fact.id}/generate-questions`, { method: 'POST' });
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function toggleTarget(target: WeeklyTarget | undefined, topic: Topic | undefined) {
    setSaving(true);
    try {
      if (target) {
        await requestJson<WeeklyTarget>(`/api/weekly-targets/${target.id}`, {
          method: 'PATCH',
          body: { active: !target.active },
        });
      } else if (topic) {
        await requestJson<Topic>(`/api/topics/${topic.id}`, {
          method: 'PATCH',
          body: { active: !topic.active },
        });
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function editTarget(target: WeeklyTarget | undefined, topic: Topic | undefined) {
    if (!topic) return;
    const nextValue = window.prompt('Weekly target value', String(target?.target_value || 1));
    if (!nextValue) return;
    const value = Number(nextValue);
    if (!Number.isFinite(value) || value < 0) return;

    setSaving(true);
    try {
      if (target) {
        await requestJson<WeeklyTarget>(`/api/weekly-targets/${target.id}`, {
          method: 'PATCH',
          body: { target_value: value },
        });
      } else {
        const type = topic.category === 'training' || topic.category === 'language' ? 'sessions' : 'blocks';
        await requestJson<WeeklyTarget>('/api/weekly-targets', {
          method: 'POST',
          body: {
            topic_id: topic.id,
            target_type: type,
            target_value: value,
            current_period_start: weekStart(today),
            active: true,
          },
        });
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  function saveSettings() {
    const nextApiBase = isFrontendApiUrl(settingsDraft.apiBase) ? defaultApi : settingsDraft.apiBase;
    localStorage.setItem('command-card-api-url', nextApiBase);
    localStorage.setItem('command-card-password', settingsDraft.appPassword);
    setApiBase(nextApiBase);
    setAppPassword(settingsDraft.appPassword);
    setSettingsDraft({ apiBase: nextApiBase, appPassword: settingsDraft.appPassword });
  }

  const quizMix = useMemo(() => {
    const counts = new Map<string, number>();
    quiz.forEach((question) => {
      const name = topicName(question.topic_id);
      counts.set(name, (counts.get(name) || 0) + 1);
    });
    return Array.from(counts.entries());
  }, [quiz, topics]);

  const workTasks = tasks.filter(taskIsWork);
  const adminTasks = tasks.filter(taskIsAdmin);
  const trainingTasks = tasks.filter(taskIsTraining);
  const missedOrRecent = tasks
    .filter((task) => task.status === 'missed' || task.status === 'skipped' || task.scheduled_date === today)
    .slice()
    .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  const topicBuckets = categoryOrder
    .map((bucket) => ({
      ...bucket,
      topics: topics
        .filter((topic) => topic.category === bucket.key)
        .slice()
        .sort((a, b) => b.priority_weight - a.priority_weight || a.name.localeCompare(b.name)),
    }))
    .filter((bucket) => bucket.topics.length);

  function renderToday() {
    return (
      <div className="page-stack">
        <Card tone="hero" className="command-card">
          <div className="command-topline">
            <div>
              <p className="eyebrow">Daily Command Card</p>
              <h2>{formatDate(today)}</h2>
            </div>
            <div className="badge-row">
              <Badge tone="accent">{titleCase(plan?.day_type || 'not generated')}</Badge>
              <Badge tone={setup.sleep_quality === 'bad' ? 'danger' : setup.sleep_quality === 'good' ? 'good' : 'warning'}>
                Sleep {setup.sleep_quality}
              </Badge>
              <Badge tone={setup.soreness === 'high' ? 'warning' : 'neutral'}>Soreness {setup.soreness}</Badge>
              <Badge tone={setup.work_pressure === 'high' ? 'warning' : 'neutral'}>Work {setup.work_pressure}</Badge>
            </div>
          </div>

          {plan?.main_focus?.topic ? (
            <>
              <div className="main-focus">
                <span className="focus-label">Focus today</span>
                <h1>{plan.main_focus.topic}</h1>
                <p>
                  One serious win is enough. Score {Math.round(plan.main_focus.score || 0)} from priority,
                  staleness, weakness, missed work, and day shape.
                </p>
              </div>

              <div className="command-grid">
                <div>
                  <span className="mini-label">Secondary</span>
                  <p>{plan.secondary_focus?.topic || 'None. Keep the day smaller.'}</p>
                </div>
                <div>
                  <span className="mini-label">Training</span>
                  <p>{plan.training?.hint || 'No training hint yet.'}</p>
                </div>
                <div>
                  <span className="mini-label">Minimum viable day</span>
                  <p>{plan.admin?.hint || 'One useful admin task if energy is low.'}</p>
                </div>
                <div>
                  <span className="mini-label">Avoid</span>
                  <p>{plan.avoid?.length ? plan.avoid.join(', ') : 'No special avoid list.'}</p>
                </div>
              </div>

              <div className="button-row">
                <Button variant="primary" onClick={() => markMainFocus('done')} disabled={saving}>
                  Done
                </Button>
                <Button onClick={() => markMainFocus('missed')} disabled={saving}>
                  Missed
                </Button>
                <Button variant="ghost" onClick={() => markMainFocus('skipped')} disabled={saving}>
                  Skip
                </Button>
              </div>
            </>
          ) : (
            <EmptyState>No plan generated yet. Generate today's plan.</EmptyState>
          )}

          <div className="command-footer">
            <Button variant="primary" onClick={generatePlan} disabled={saving}>
              Generate today's plan
            </Button>
            {loading ? <span className="muted">Refreshing...</span> : null}
          </div>
        </Card>

        <div className="two-column">
          <Card>
            <SectionHeader eyebrow="Setup" title="Daily setup" />
            <div className="setup-block">
              <label>Sleep</label>
              <SegmentedControl
                value={setup.sleep_quality}
                options={[
                  { value: 'bad', label: 'Bad' },
                  { value: 'meh', label: 'Meh' },
                  { value: 'good', label: 'Good' },
                ]}
                onChange={(value) => setSetup((current) => ({ ...current, sleep_quality: value }))}
              />
            </div>
            <div className="setup-block">
              <label>Soreness</label>
              <SegmentedControl
                value={setup.soreness}
                options={[
                  { value: 'low', label: 'Low' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'high', label: 'High' },
                ]}
                onChange={(value) => setSetup((current) => ({ ...current, soreness: value }))}
              />
            </div>
            <div className="setup-block">
              <label>Work pressure</label>
              <SegmentedControl
                value={setup.work_pressure}
                options={[
                  { value: 'low', label: 'Low' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'high', label: 'High' },
                ]}
                onChange={(value) => setSetup((current) => ({ ...current, work_pressure: value }))}
              />
            </div>
            <div className="setup-block">
              <label>Training today</label>
              <SegmentedControl
                value={setup.training}
                options={[
                  { value: 'none', label: 'None' },
                  { value: 'bjj', label: 'BJJ' },
                  { value: 'lifting', label: 'Lifting' },
                  { value: 'both', label: 'Both' },
                  { value: 'other', label: 'Other' },
                ]}
                onChange={(value) => setSetup((current) => ({ ...current, training: value }))}
              />
            </div>
            <Button variant="primary" onClick={saveDailySetup} disabled={saving}>
              Save setup
            </Button>
          </Card>

          <Card>
            <SectionHeader eyebrow="Work" title="One task that matters" />
            <label className="field-label" htmlFor="work-task">
              What is the one work task that matters today?
            </label>
            <div className="inline-form">
              <input
                id="work-task"
                value={workTaskTitle}
                onChange={(event) => setWorkTaskTitle(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') addWorkTask();
                }}
                placeholder="Write the concrete work win"
              />
              <Button variant="primary" onClick={addWorkTask} disabled={saving || !workTaskTitle.trim()}>
                Add
              </Button>
            </div>
            <TaskPreviewList tasks={workTasks.filter((task) => task.scheduled_date === today).slice(0, 4)} topicName={topicName} onStatus={updateTaskStatus} />
          </Card>
        </div>

        <div className="two-column">
          <Card>
            <SectionHeader
              eyebrow="Review"
              title="Today's quiz"
              action={
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    setActiveTab('Quiz');
                    setQuizIndex(0);
                  }}
                >
                  Start quiz
                </Button>
              }
            />
            <div className="quiz-summary">
              {quizMix.length ? (
                <div className="topic-mix">
                  {quizMix.map(([name, count]) => (
                    <Badge key={name} tone="neutral">
                      {name} {count}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="muted">No quiz selected yet. Generate the plan to refresh the queue.</p>
              )}
              <DdiaChapterSelector
                available={ddiaSettings.available_chapters}
                selected={selectedDdiaChapters}
                onToggle={toggleDdiaChapter}
                onSave={() => saveDdiaChapters()}
                saving={saving}
                compact
              />
            </div>
          </Card>

          <Card>
            <SectionHeader eyebrow="Support" title="Admin / Life support" />
            <div className="inline-form">
              <input
                value={adminTaskTitle}
                onChange={(event) => setAdminTaskTitle(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') addAdminTask();
                }}
                placeholder="Laundry, bills, texts, email"
              />
              <Button variant="primary" onClick={() => addAdminTask()} disabled={saving || !adminTaskTitle.trim()}>
                Add
              </Button>
            </div>
            <div className="quick-chips">
              {['Laundry', 'Bills', 'Texts', 'Email', 'Meal prep'].map((example) => (
                <button key={example} type="button" onClick={() => addAdminTask(example)}>
                  {example}
                </button>
              ))}
            </div>
            <TaskPreviewList tasks={adminTasks.filter((task) => task.status === 'planned').slice(0, 4)} topicName={topicName} onStatus={updateTaskStatus} />
          </Card>
        </div>
      </div>
    );
  }

  function renderQuiz() {
    const question = quiz[quizIndex];
    const fact = question ? factById.get(question.fact_id) : undefined;
    const source = fact ? sourceById.get(fact.source_id) : undefined;
    const topic = question ? topicById.get(question.topic_id) : undefined;
    const choices = getChoices(question);
    const sourceCitation = getSourceCitation(question) || source?.source_ref || '';
    const complete = quiz.length > 0 && quizIndex >= quiz.length;

    return (
      <div className="page-stack narrow">
        <Card>
          <SectionHeader eyebrow="Focused review" title="Quiz session" />
          {quiz.length ? (
            <>
              <div className="quiz-progress">
                <span>{complete ? 'Session complete' : `Question ${quizIndex + 1} of ${quiz.length}`}</span>
                <ProgressBar value={complete ? 100 : ((quizIndex + 1) / quiz.length) * 100} />
              </div>

              {question && !complete ? (
                <>
                  <div className="badge-row quiz-meta">
                    <Badge tone="accent">{topic?.name || 'Topic'}</Badge>
                    {fact?.tags?.map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                    {source?.title ? <Badge>{source.title}</Badge> : null}
                  </div>

                  <div className="prompt-card">
                    <p>{question.prompt}</p>
                  </div>

                  {choices.length ? (
                    <div className="choice-list" role="radiogroup" aria-label="Answer choices">
                      {choices.map((choice) => {
                        const selected =
                          normalizedAnswer(answer) === normalizedAnswer(choice.label) ||
                          normalizedAnswer(answer) === normalizedAnswer(choice.text) ||
                          normalizedAnswer(answer) === normalizedAnswer(`${choice.label}. ${choice.text}`);
                        const isCorrect = question.correct_choice
                          ? normalizedAnswer(choice.label) === normalizedAnswer(question.correct_choice)
                          : normalizedAnswer(choice.text) === normalizedAnswer(question.correct_answer);
                        return (
                          <button
                            key={`${choice.label}-${choice.text}`}
                            type="button"
                            className={[
                              'choice',
                              selected ? 'selected' : '',
                              answerRevealed && isCorrect ? 'correct' : '',
                              answerRevealed && selected && !isCorrect ? 'incorrect' : '',
                            ]
                              .filter(Boolean)
                              .join(' ')}
                            onClick={() => setAnswer(choice.label)}
                            disabled={answerRevealed}
                            role="radio"
                            aria-checked={selected}
                          >
                            <span>{choice.label}</span>
                            <strong>{choice.text}</strong>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <>
                      <label className="field-label" htmlFor="quiz-answer">
                        Your answer
                      </label>
                      <textarea
                        id="quiz-answer"
                        value={answer}
                        onChange={(event) => setAnswer(event.target.value)}
                        onKeyDown={(event) => {
                          if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                            event.preventDefault();
                            revealAnswer();
                          }
                        }}
                        placeholder="Answer from memory. Cmd/Ctrl+Enter reveals the answer."
                      />
                    </>
                  )}

                  <div className="button-row">
                    <Button variant="primary" onClick={revealAnswer} disabled={answerRevealed || (choices.length > 0 && !answer)}>
                      Submit
                    </Button>
                    <Button variant="ghost" onClick={moveToNextQuestion}>
                      Skip
                    </Button>
                  </div>

                  {answerRevealed ? (
                    <div className="answer-panel">
                      <div>
                        <span className="mini-label">Correct answer</span>
                        <p>
                          {question.correct_choice ? `${question.correct_choice}. ` : ''}
                          {question.correct_answer}
                        </p>
                      </div>
                      <div>
                        <span className="mini-label">Explanation</span>
                        <p>{question.explanation || fact?.explanation || 'No explanation saved.'}</p>
                      </div>
                      {sourceCitation ? (
                        <div>
                          <span className="mini-label">Source</span>
                          <p className="source-ref">{sourceCitation}</p>
                        </div>
                      ) : null}
                      <div>
                        <span className="mini-label">Why this appeared</span>
                        <p>
                          {topic?.name === plan?.main_focus?.topic
                            ? 'Current focus bonus.'
                            : 'Selected by due date, weakness, importance, and review rotation.'}
                        </p>
                      </div>
                      {quizFeedback ? <p className="muted">{quizFeedback}</p> : null}
                      <div className="grade-grid">
                        {(['again', 'hard', 'good', 'easy'] as Grade[]).map((grade, index) => (
                          <Button key={grade} onClick={() => gradeQuestion(grade)} disabled={saving}>
                            {index + 1}. {titleCase(grade)}
                          </Button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                <EmptyState>
                  Review complete. Start another session after the planner selects the next set.
                </EmptyState>
              )}
            </>
          ) : (
            <EmptyState>No quiz cards selected yet. Generate today's plan or add approved facts.</EmptyState>
          )}
        </Card>
      </div>
    );
  }

  function renderTasks() {
    return (
      <div className="page-stack">
        <div className="two-column">
          <Card>
            <SectionHeader eyebrow="Work" title="Work tasks" />
            <div className="inline-form">
              <input
                value={workTaskTitle}
                onChange={(event) => setWorkTaskTitle(event.target.value)}
                placeholder="Add the next work task"
              />
              <Button variant="primary" onClick={addWorkTask} disabled={saving || !workTaskTitle.trim()}>
                Add
              </Button>
            </div>
            <TaskList tasks={workTasks} topicName={topicName} onStatus={updateTaskStatus} empty="No work tasks yet." />
          </Card>

          <Card>
            <SectionHeader eyebrow="Admin" title="Admin tasks" />
            <div className="inline-form">
              <input
                value={adminTaskTitle}
                onChange={(event) => setAdminTaskTitle(event.target.value)}
                placeholder="Add admin or life task"
              />
              <Button variant="primary" onClick={() => addAdminTask()} disabled={saving || !adminTaskTitle.trim()}>
                Add
              </Button>
            </div>
            <TaskList
              tasks={adminTasks}
              topicName={topicName}
              onStatus={updateTaskStatus}
              empty="No admin items yet. Add bills, laundry, texts, or email."
            />
          </Card>
        </div>

        <div className="two-column">
          <Card>
            <SectionHeader eyebrow="Training" title="Training logs" />
            {events.length || trainingTasks.length ? (
              <div className="compact-list">
                {events.map((event) => (
                  <div className="list-item" key={`event-${event.id}`}>
                    <div>
                      <strong>{event.title}</strong>
                      <span>{new Date(event.start_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
                    </div>
                    <Badge>{event.source}</Badge>
                  </div>
                ))}
                {trainingTasks.map((task) => (
                  <TaskRow key={task.id} task={task} topicName={topicName} onStatus={updateTaskStatus} />
                ))}
              </div>
            ) : (
              <EmptyState>No training logged today.</EmptyState>
            )}
          </Card>

          <Card>
            <SectionHeader eyebrow="Recent" title="Missed / recent tasks" />
            <TaskList
              tasks={missedOrRecent}
              topicName={topicName}
              onStatus={updateTaskStatus}
              empty="No recent or missed tasks."
            />
          </Card>
        </div>
      </div>
    );
  }

  function renderTargets() {
    return (
      <div className="page-stack">
        {topicBuckets.map((bucket) => (
          <TargetBucket
            key={bucket.key}
            title={bucket.title}
            bucketTopics={bucket.topics}
            targets={targets}
            tasks={tasks}
            today={today}
            onToggle={toggleTarget}
            onEdit={editTarget}
          />
        ))}
      </div>
    );
  }

  function renderNotes() {
    return (
      <div className="page-stack">
        <Card>
          <SectionHeader eyebrow="Step 1" title="Add source note" />
          <div className="notes-grid">
            <label>
              Topic
              <select
                value={noteTopicId}
                onChange={(event) => setNoteTopicId(event.target.value ? Number(event.target.value) : '')}
              >
                <option value="">Choose topic</option>
                {topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source title
              <input
                value={noteTitle}
                onChange={(event) => setNoteTitle(event.target.value)}
                placeholder="Book chapter, lesson, roll notes"
              />
            </label>
          </div>
          <label className="field-label" htmlFor="source-note">
            Paste a source-backed note
          </label>
          <textarea
            id="source-note"
            className="source-note"
            value={noteText}
            onChange={(event) => setNoteText(event.target.value)}
            placeholder="Paste notes with facts worth remembering. Each line can become a candidate fact."
          />
          <Button variant="primary" onClick={extractFacts} disabled={saving || !noteText.trim() || !noteTopicId}>
            Extract candidate facts
          </Button>
        </Card>

        <Card>
          <SectionHeader eyebrow="Step 2" title="Review extracted facts" />
          {facts.length ? (
            <div className="fact-grid">
              {facts.map((fact) => (
                <FactCard
                  key={fact.id}
                  fact={fact}
                  topic={topicById.get(fact.topic_id)}
                  source={sourceById.get(fact.source_id)}
                  onApprove={() => reviewFact(fact, 'approve')}
                  onReject={() => reviewFact(fact, 'reject')}
                  onEdit={() => {
                    const next = window.prompt('Edit fact text', fact.fact_text);
                    if (next && next !== fact.fact_text) patchFact(fact, { fact_text: next });
                  }}
                />
              ))}
            </div>
          ) : (
            <EmptyState>No facts waiting. Paste a note to create source-backed quiz material.</EmptyState>
          )}
        </Card>

        <Card>
          <SectionHeader eyebrow="Step 3" title="Generate questions from approved facts" />
          {approvedFacts.length ? (
            <div className="fact-grid">
              {approvedFacts.slice(0, 8).map((fact) => (
                <FactCard
                  key={fact.id}
                  fact={fact}
                  topic={topicById.get(fact.topic_id)}
                  source={sourceById.get(fact.source_id)}
                  onGenerate={() => generateQuestions(fact)}
                />
              ))}
            </div>
          ) : (
            <EmptyState>Approved facts will appear here after review.</EmptyState>
          )}
        </Card>
      </div>
    );
  }

  function renderSettings() {
    return (
      <div className="page-stack narrow">
        <Card>
          <SectionHeader eyebrow="Connection" title="API settings" />
          <label>
            API URL
            <input
              value={settingsDraft.apiBase}
              onChange={(event) => setSettingsDraft((current) => ({ ...current, apiBase: event.target.value }))}
            />
          </label>
          <label>
            App password
            <input
              type="password"
              value={settingsDraft.appPassword}
              onChange={(event) => setSettingsDraft((current) => ({ ...current, appPassword: event.target.value }))}
              placeholder="x-app-password"
            />
          </label>
          <p className="muted">
            OpenAI API keys stay server-side in the backend environment. This browser only stores the local app
            password used for API requests.
          </p>
          <div className="button-row">
            <Button variant="primary" onClick={saveSettings}>
              Save settings
            </Button>
            <Button onClick={loadData}>Test connection</Button>
          </div>
        </Card>

        <Card>
          <SectionHeader eyebrow="Planner" title="Daily defaults" />
          <div className="settings-list">
            <div>
              <strong>Quiz size</strong>
              <span>Controlled by planner day type. No frontend override exists yet.</span>
            </div>
            <div>
              <strong>DDIA chapter filter</strong>
              <span>
                {selectedDdiaChapters.length
                  ? `Testing chapters ${selectedDdiaChapters.join(', ')}`
                  : 'All imported DDIA chapters are eligible.'}
              </span>
              <DdiaChapterSelector
                available={ddiaSettings.available_chapters}
                selected={selectedDdiaChapters}
                onToggle={toggleDdiaChapter}
                onSave={() => saveDdiaChapters()}
                onClear={() => saveDdiaChapters([])}
                saving={saving}
              />
            </div>
            <div>
              <strong>Debug</strong>
              <span>{apiBase}</span>
            </div>
          </div>
          <Button onClick={generatePlan} disabled={saving}>
            Regenerate plan
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-block">
          <h1>Command Card</h1>
          <p>One useful day, not a second job.</p>
        </div>
        <nav className="tabs" aria-label="Main navigation">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              className={activeTab === tab ? 'tab active' : 'tab'}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>
      </header>

      {error ? (
        <div className="notice" role="alert">
          {error}
        </div>
      ) : null}

      <main>
        {activeTab === 'Today' ? renderToday() : null}
        {activeTab === 'Quiz' ? renderQuiz() : null}
        {activeTab === 'Tasks' ? renderTasks() : null}
        {activeTab === 'Targets' ? renderTargets() : null}
        {activeTab === 'Notes' ? renderNotes() : null}
        {activeTab === 'Settings' ? renderSettings() : null}
      </main>
    </div>
  );
}

function DdiaChapterSelector({
  available,
  selected,
  onToggle,
  onSave,
  onClear,
  saving,
  compact = false,
}: {
  available: number[];
  selected: number[];
  onToggle: (chapter: number) => void;
  onSave: () => void;
  onClear?: () => void;
  saving: boolean;
  compact?: boolean;
}) {
  if (!available.length) {
    return compact ? null : <p className="muted">No sourced DDIA chapters imported yet.</p>;
  }

  return (
    <div className={compact ? 'chapter-control compact' : 'chapter-control'}>
      <div className="chapter-grid">
        {available.map((chapter) => (
          <button
            key={chapter}
            type="button"
            className={selected.includes(chapter) ? 'chapter-option selected' : 'chapter-option'}
            onClick={() => onToggle(chapter)}
          >
            Ch. {chapter}
          </button>
        ))}
      </div>
      <div className="button-row">
        <Button size="sm" variant="primary" onClick={onSave} disabled={saving}>
          Save DDIA chapters
        </Button>
        {onClear ? (
          <Button size="sm" variant="ghost" onClick={onClear} disabled={saving || !selected.length}>
            Test all
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function TaskPreviewList({
  tasks,
  topicName,
  onStatus,
}: {
  tasks: Task[];
  topicName: (topicId?: number | null) => string;
  onStatus: (task: Task, status: TaskStatus) => void;
}) {
  if (!tasks.length) return <EmptyState>No tasks yet.</EmptyState>;
  return (
    <div className="compact-list">
      {tasks.map((task, index) => (
        <TaskRow key={task.id} task={task} topicName={topicName} onStatus={onStatus} compact priority={index === 0} />
      ))}
    </div>
  );
}

function TaskList({
  tasks,
  topicName,
  onStatus,
  empty,
}: {
  tasks: Task[];
  topicName: (topicId?: number | null) => string;
  onStatus: (task: Task, status: TaskStatus) => void;
  empty: string;
}) {
  if (!tasks.length) return <EmptyState>{empty}</EmptyState>;
  return (
    <div className="compact-list">
      {tasks.map((task) => (
        <TaskRow key={task.id} task={task} topicName={topicName} onStatus={onStatus} />
      ))}
    </div>
  );
}

function TaskRow({
  task,
  topicName,
  onStatus,
  compact = false,
  priority = false,
}: {
  task: Task;
  topicName: (topicId?: number | null) => string;
  onStatus: (task: Task, status: TaskStatus) => void;
  compact?: boolean;
  priority?: boolean;
}) {
  return (
    <div className={priority ? 'task-row priority' : 'task-row'}>
      <div className="task-main">
        <strong>{task.title}</strong>
        <span>
          {topicName(task.topic_id)} / {task.status}
          {task.scheduled_date ? ` / ${task.scheduled_date}` : ''}
        </span>
      </div>
      {!compact || task.status === 'planned' ? (
        <div className="task-actions">
          <Button size="sm" onClick={() => onStatus(task, 'done')} disabled={task.status === 'done'}>
            Done
          </Button>
          <Button size="sm" onClick={() => onStatus(task, 'missed')} disabled={task.status === 'missed'}>
            Missed
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onStatus(task, 'skipped')} disabled={task.status === 'skipped'}>
            Skip
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function TargetBucket({
  title,
  bucketTopics,
  targets,
  tasks,
  today,
  onToggle,
  onEdit,
}: {
  title: string;
  bucketTopics: Topic[];
  targets: WeeklyTarget[];
  tasks: Task[];
  today: string;
  onToggle: (target: WeeklyTarget | undefined, topic: Topic | undefined) => void;
  onEdit: (target: WeeklyTarget | undefined, topic: Topic | undefined) => void;
}) {
  return (
    <Card>
      <SectionHeader eyebrow="Goals" title={title} />
      <div className="target-grid">
        {bucketTopics.map((topic) => {
          const target = targets.find((item) => item.topic_id === topic.id);
          const start = target?.current_period_start || weekStart(today);
          const done = tasks.filter(
            (task) =>
              task.topic_id === topic.id &&
              task.status === 'done' &&
              String(task.scheduled_date || task.completed_at || '').slice(0, 10) >= start,
          ).length;
          const targetValue = target?.target_value || 0;
          const progress = targetValue ? (done / targetValue) * 100 : 0;

          return (
            <div className="target-card" key={topic.id}>
              <div className="target-top">
                <div>
                  <strong>{topic.name}</strong>
                  <span>{displayCategory(topic.category)}</span>
                </div>
                <Badge tone={target?.active && topic.active ? 'good' : 'neutral'}>
                  {target?.active && topic.active ? 'Active' : 'Off'}
                </Badge>
              </div>
              <p>
                {target
                  ? `${done}/${target.target_value} ${target.target_type} this week`
                  : 'No weekly target set'}
              </p>
              <ProgressBar value={progress} />
              <div className="target-meta">
                <span>Priority {topic.priority_weight}</span>
                <div>
                  <Button size="sm" onClick={() => onToggle(target, topic)}>
                    Toggle
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => onEdit(target, topic)}>
                    Edit
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function TargetGroup({
  title,
  names,
  topics,
  targets,
  tasks,
  today,
  onToggle,
  onEdit,
}: {
  title: string;
  names: string[];
  topics: Topic[];
  targets: WeeklyTarget[];
  tasks: Task[];
  today: string;
  onToggle: (target: WeeklyTarget | undefined, topic: Topic | undefined) => void;
  onEdit: (target: WeeklyTarget | undefined, topic: Topic | undefined) => void;
}) {
  return (
    <Card>
      <SectionHeader eyebrow="Weekly" title={title} />
      <div className="target-grid">
        {names.map((name) => {
          const topic = topics.find((item) => item.name.toLowerCase() === name.toLowerCase());
          const target = topic ? targets.find((item) => item.topic_id === topic.id) : undefined;
          const start = target?.current_period_start || weekStart(today);
          const done = topic
            ? tasks.filter(
                (task) =>
                  task.topic_id === topic.id &&
                  task.status === 'done' &&
                  String(task.scheduled_date || task.completed_at || '').slice(0, 10) >= start,
              ).length
            : 0;
          const targetValue = target?.target_value || 0;
          const progress = targetValue ? (done / targetValue) * 100 : 0;

          return (
            <div className={topic ? 'target-card' : 'target-card ghosted'} key={name}>
              <div className="target-top">
                <div>
                  <strong>{name}</strong>
                  <span>{topic ? titleCase(topic.category) : 'Not in inventory'}</span>
                </div>
                <Badge tone={target?.active || topic?.active ? 'good' : 'neutral'}>
                  {target?.active || topic?.active ? 'Active' : 'Off'}
                </Badge>
              </div>
              <p>
                {target
                  ? `${name}: ${done}/${target.target_value} ${target.target_type}`
                  : topic
                    ? 'No weekly target set'
                    : 'Topic not created yet'}
              </p>
              <ProgressBar value={progress} />
              <div className="target-meta">
                <span>Priority {topic?.priority_weight ?? '-'}</span>
                <div>
                  <Button size="sm" onClick={() => onToggle(target, topic)} disabled={!topic}>
                    Toggle
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => onEdit(target, topic)} disabled={!topic}>
                    Edit
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function FactCard({
  fact,
  topic,
  source,
  onApprove,
  onReject,
  onEdit,
  onGenerate,
}: {
  fact: Fact;
  topic?: Topic;
  source?: Source;
  onApprove?: () => void;
  onReject?: () => void;
  onEdit?: () => void;
  onGenerate?: () => void;
}) {
  return (
    <div className="fact-card">
      <div className="badge-row">
        <Badge tone="accent">{topic?.name || 'Topic'}</Badge>
        {source?.title ? <Badge>{source.title}</Badge> : null}
      </div>
      <p className="fact-text">{fact.fact_text}</p>
      <p className="muted">{fact.explanation}</p>
      {fact.tags?.length ? (
        <div className="tag-row">
          {fact.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      ) : null}
      <div className="button-row">
        {onApprove ? (
          <Button size="sm" variant="primary" onClick={onApprove}>
            Approve
          </Button>
        ) : null}
        {onReject ? (
          <Button size="sm" variant="danger" onClick={onReject}>
            Reject
          </Button>
        ) : null}
        {onEdit ? (
          <Button size="sm" variant="ghost" onClick={onEdit}>
            Edit
          </Button>
        ) : null}
        {onGenerate ? (
          <Button size="sm" variant="primary" onClick={onGenerate}>
            Generate questions
          </Button>
        ) : null}
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
