import React, { useEffect, useMemo, useState } from 'react';
import api from '../services/api';

const GOLD_TASKS = [
  'text',
  'reading_order',
  'headings',
  'lists',
  'tables',
  'figures',
  'captions',
  'footnotes',
  'formulas',
];

const GOLD_TYPES = [
  'heading',
  'paragraph',
  'list_item',
  'table',
  'figure',
  'caption',
  'footnote',
  'formula',
  'text_block',
];

function decisionKey(subject, subjectId) {
  return `${subject}:${subjectId}`;
}

function statusLabel(value) {
  if (value === 'reviewed') return 'Reviewed';
  if (value === 'draft') return 'Draft';
  return 'Unannotated';
}

function errorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.message ||
    'Gold review operation failed'
  );
}

function GoldReviewWorkbench() {
  const [queue, setQueue] = useState([]);
  const [session, setSession] = useState(null);
  const [reviewer, setReviewer] = useState('');
  const [backend, setBackend] = useState('pymupdf');
  const [loadingTarget, setLoadingTarget] = useState('');
  const [busyAction, setBusyAction] = useState('');
  const [error, setError] = useState('');
  const [elementDrafts, setElementDrafts] = useState({});
  const [readingOrderDraft, setReadingOrderDraft] = useState('');
  const [promotionNote, setPromotionNote] = useState('');
  const [newElement, setNewElement] = useState({
    id: '',
    type: 'heading',
    text: '',
    level: '1',
    bbox: null,
  });

  const loadQueue = async () => {
    try {
      const response = await api.getGoldReviewQueue();
      setQueue(response.data.items || []);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  useEffect(() => {
    if (!session) {
      setElementDrafts({});
      setReadingOrderDraft('');
      return;
    }
    const drafts = {};
    (session.page?.elements || []).forEach((element) => {
      drafts[element.id] = {
        ...element,
        level:
          element.level === undefined || element.level === null
            ? ''
            : String(element.level),
      };
    });
    setElementDrafts(drafts);
    setReadingOrderDraft((session.page?.reading_order || []).join('\n'));
  }, [session]);

  const decisions = useMemo(() => {
    const result = {};
    (session?.decisions || []).forEach((decision) => {
      result[decisionKey(decision.subject, decision.subject_id)] = decision;
    });
    return result;
  }, [session]);

  const runAction = async (name, action) => {
    setBusyAction(name);
    setError('');
    try {
      const response = await action();
      if (response?.data) {
        setSession(response.data);
      }
      return response;
    } catch (err) {
      setError(errorMessage(err));
      return null;
    } finally {
      setBusyAction('');
    }
  };

  const openTarget = async (item) => {
    const key = `${item.document_id}:${item.page_index}`;
    setLoadingTarget(key);
    setError('');
    try {
      const response = await api.createGoldReviewSession(
        item.document_id,
        item.page_index,
        backend
      );
      setSession(response.data);
      setPromotionNote('');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingTarget('');
    }
  };

  const requireReviewer = () => {
    if (!reviewer.trim()) {
      setError('Enter reviewer identity before confirming review items.');
      return false;
    }
    return true;
  };

  const confirmItem = async (subject, subjectId) => {
    if (!requireReviewer()) return;
    await runAction(`confirm:${subject}:${subjectId}`, () =>
      api.confirmGoldReviewItem(
        session.id,
        subject,
        subjectId,
        reviewer.trim()
      )
    );
  };

  const toggleTask = async (task) => {
    const current = new Set(session.page?.tasks || []);
    if (current.has(task)) current.delete(task);
    else current.add(task);
    const tasks = GOLD_TASKS.filter((item) => current.has(item));
    if (tasks.length === 0) {
      setError('At least one gold task must remain enabled.');
      return;
    }
    await runAction('tasks', () => api.setGoldReviewTasks(session.id, tasks));
  };

  const updateDraft = (elementId, field, value) => {
    setElementDrafts((current) => ({
      ...current,
      [elementId]: {
        ...current[elementId],
        [field]: value,
      },
    }));
  };

  const saveElement = async (elementId) => {
    const draft = elementDrafts[elementId];
    if (!draft) return;
    const payload = {
      id: draft.id,
      type: draft.type,
      text: draft.text || '',
      attrs: draft.attrs || {},
    };
    if (draft.bbox) payload.bbox = draft.bbox;
    if (draft.type === 'heading' && draft.level !== '') {
      payload.level = Number(draft.level);
    }
    await runAction(`save:${elementId}`, () =>
      api.upsertGoldReviewElement(session.id, payload)
    );
  };

  const deleteElement = async (elementId) => {
    await runAction(`delete:${elementId}`, () =>
      api.deleteGoldReviewElement(session.id, elementId)
    );
  };

  const seedFromParserNode = (node) => {
    const suffix = (session.page?.elements || []).length + 1;
    setNewElement({
      id: `p${session.page_index}-e${suffix}`,
      type: node.type === 'text_block' ? 'paragraph' : node.type,
      text: node.text || '',
      level: node.type === 'heading' ? '1' : '',
      bbox: node.bbox || null,
    });
  };

  const addElement = async () => {
    if (!newElement.id.trim()) {
      setError('New gold element requires a stable id.');
      return;
    }
    const payload = {
      id: newElement.id.trim(),
      type: newElement.type,
      text: newElement.text || '',
      attrs: {},
    };
    if (newElement.bbox) payload.bbox = newElement.bbox;
    if (newElement.type === 'heading' && newElement.level !== '') {
      payload.level = Number(newElement.level);
    }
    const response = await runAction('add-element', () =>
      api.upsertGoldReviewElement(session.id, payload)
    );
    if (response) {
      setNewElement({
        id: '',
        type: 'heading',
        text: '',
        level: '1',
        bbox: null,
      });
    }
  };

  const saveReadingOrder = async () => {
    const order = readingOrderDraft
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean);
    await runAction('reading-order', () =>
      api.setGoldReviewReadingOrder(session.id, order)
    );
  };

  const promote = async () => {
    if (!requireReviewer()) return;
    await runAction('promote', () =>
      api.promoteGoldReview(
        session.id,
        reviewer.trim(),
        promotionNote.trim()
      )
    );
  };

  const publish = async () => {
    const response = await runAction('publish', () =>
      api.publishGoldReview(session.id)
    );
    if (response) {
      await loadQueue();
    }
  };

  const renderOverlay = (item, className, label) => {
    if (!item.bbox || !session?.page?.width || !session?.page?.height) {
      return null;
    }
    const [x0, y0, x1, y1] = item.bbox;
    const style = {
      left: `${(x0 / session.page.width) * 100}%`,
      top: `${(y0 / session.page.height) * 100}%`,
      width: `${((x1 - x0) / session.page.width) * 100}%`,
      height: `${((y1 - y0) / session.page.height) * 100}%`,
    };
    return (
      <button
        key={item.id}
        type="button"
        className={className}
        style={style}
        title={label}
        onClick={() => className.includes('parser') && seedFromParserNode(item)}
      >
        <span>{label}</span>
      </button>
    );
  };

  const preflight = session?.preflight || {
    ready: false,
    blockers: [],
  };
  const promoted = session?.promoted_annotation;
  const queueGroups = useMemo(() => {
    const groups = {};
    queue.forEach((item) => {
      if (!groups[item.document_id]) {
        groups[item.document_id] = {
          title: item.title,
          language: item.language,
          items: [],
        };
      }
      groups[item.document_id].items.push(item);
    });
    return groups;
  }, [queue]);

  return (
    <div className="gold-workbench">
      <div className="gold-workbench-toolbar">
        <div>
          <h2>Gold Annotation Review</h2>
          <p>
            Review source-pinned pages, confirm gold semantics, then promote
            and explicitly publish reviewed annotations.
          </p>
        </div>
        <div className="gold-review-identity">
          <label>
            Reviewer
            <input
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              placeholder="name or reviewer id"
            />
          </label>
          <label>
            Parser overlay
            <select
              value={backend}
              onChange={(event) => setBackend(event.target.value)}
            >
              <option value="pymupdf">PyMuPDF</option>
              <option value="mineru">MinerU</option>
              <option value="marker">Marker</option>
            </select>
          </label>
        </div>
      </div>

      {error && <div className="gold-review-error">{error}</div>}

      <div className="gold-workbench-grid">
        <aside className="gold-review-queue">
          <div className="gold-panel-title">
            <strong>Review queue</strong>
            <span>{queue.length} pages</span>
          </div>
          {Object.entries(queueGroups).map(([documentId, group]) => (
            <section key={documentId} className="gold-queue-document">
              <div>
                <strong>{group.title}</strong>
                <span>
                  {documentId} · {group.language}
                </span>
              </div>
              {group.items.map((item) => {
                const targetKey = `${item.document_id}:${item.page_index}`;
                const active =
                  session?.document_id === item.document_id &&
                  session?.page_index === item.page_index;
                return (
                  <button
                    key={targetKey}
                    type="button"
                    className={[
                      'gold-queue-target',
                      active ? 'active' : '',
                    ].join(' ')}
                    onClick={() => openTarget(item)}
                    disabled={loadingTarget === targetKey}
                  >
                    <span>PDF page {item.page_index}</span>
                    <span className={`gold-status ${item.annotation_status}`}>
                      {statusLabel(item.annotation_status)}
                    </span>
                    <small>{item.tasks.join(', ')}</small>
                  </button>
                );
              })}
            </section>
          ))}
        </aside>

        <main className="gold-review-canvas">
          {!session && (
            <div className="gold-review-placeholder">
              Choose a review target to materialize its exact pinned PDF and
              build a parser overlay.
            </div>
          )}
          {session && (
            <>
              <div className="gold-panel-title">
                <div>
                  <strong>{session.document_id}</strong>
                  <span>
                    page {session.page_index} · {session.backend}
                  </span>
                </div>
                <code>{session.source_sha256.slice(0, 16)}…</code>
              </div>
              <div className="gold-page-stage">
                <img
                  src={api.getGoldReviewPageUrl(session.id)}
                  alt={`PDF page ${session.page_index}`}
                />
                <div className="gold-page-overlays">
                  {(session.parser_nodes || []).map((node) =>
                    renderOverlay(
                      node,
                      'gold-overlay parser',
                      `P · ${node.type}`
                    )
                  )}
                  {(session.page?.elements || []).map((element) =>
                    renderOverlay(
                      element,
                      'gold-overlay gold',
                      `G · ${element.id}`
                    )
                  )}
                </div>
              </div>
              <div className="gold-overlay-legend">
                <span><i className="parser" /> Parser block — click to seed element</span>
                <span><i className="gold" /> Gold bbox</span>
              </div>
              <details className="gold-evidence">
                <summary>Current deterministic evaluator evidence</summary>
                <pre>{JSON.stringify(session.evaluation, null, 2)}</pre>
              </details>
            </>
          )}
        </main>

        <aside className="gold-review-editor">
          {!session && (
            <div className="gold-review-placeholder">
              Review controls appear after opening a queue target.
            </div>
          )}
          {session && (
            <>
              <section className="gold-editor-section">
                <div className="gold-panel-title">
                  <strong>Tasks</strong>
                  <span>confirm completeness, not mere presence</span>
                </div>
                <div className="gold-task-grid">
                  {GOLD_TASKS.map((task) => {
                    const enabled = (session.page?.tasks || []).includes(task);
                    const confirmed =
                      decisions[decisionKey('task', task)] !== undefined;
                    return (
                      <div
                        key={task}
                        className={[
                          'gold-task',
                          enabled ? 'enabled' : '',
                          confirmed ? 'confirmed' : '',
                        ].join(' ')}
                      >
                        <label>
                          <input
                            type="checkbox"
                            checked={enabled}
                            onChange={() => toggleTask(task)}
                            disabled={busyAction === 'tasks'}
                          />
                          {task}
                        </label>
                        {enabled && (
                          <button
                            type="button"
                            onClick={() => confirmItem('task', task)}
                            disabled={confirmed || busyAction.startsWith('confirm:')}
                          >
                            {confirmed ? 'Confirmed' : 'Confirm'}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="gold-editor-section">
                <div className="gold-panel-title">
                  <strong>Elements</strong>
                  <span>{session.page?.elements?.length || 0}</span>
                </div>
                <div className="gold-element-list">
                  {(session.page?.elements || []).map((element) => {
                    const draft = elementDrafts[element.id] || element;
                    const confirmed =
                      decisions[decisionKey('element', element.id)] !== undefined;
                    return (
                      <article
                        key={element.id}
                        className={[
                          'gold-element-card',
                          confirmed ? 'confirmed' : '',
                        ].join(' ')}
                      >
                        <div className="gold-element-row">
                          <code>{element.id}</code>
                          <span>{confirmed ? 'confirmed' : 'pending'}</span>
                        </div>
                        <label>
                          Type
                          <select
                            value={draft.type}
                            onChange={(event) =>
                              updateDraft(element.id, 'type', event.target.value)
                            }
                          >
                            {GOLD_TYPES.map((type) => (
                              <option key={type} value={type}>{type}</option>
                            ))}
                          </select>
                        </label>
                        {draft.type === 'heading' && (
                          <label>
                            Heading level
                            <input
                              type="number"
                              min="1"
                              max="6"
                              value={draft.level}
                              onChange={(event) =>
                                updateDraft(element.id, 'level', event.target.value)
                              }
                            />
                          </label>
                        )}
                        <label>
                          Text
                          <textarea
                            value={draft.text || ''}
                            onChange={(event) =>
                              updateDraft(element.id, 'text', event.target.value)
                            }
                          />
                        </label>
                        {element.bbox && (
                          <small>BBox: {element.bbox.join(', ')}</small>
                        )}
                        <div className="gold-element-actions">
                          <button
                            type="button"
                            onClick={() => saveElement(element.id)}
                            disabled={busyAction === `save:${element.id}`}
                          >
                            Save edit
                          </button>
                          <button
                            type="button"
                            onClick={() => confirmItem('element', element.id)}
                            disabled={confirmed || busyAction.startsWith('confirm:')}
                          >
                            {confirmed ? 'Confirmed' : 'Confirm'}
                          </button>
                          <button
                            type="button"
                            className="danger"
                            onClick={() => deleteElement(element.id)}
                            disabled={busyAction === `delete:${element.id}`}
                          >
                            Delete
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>

                <article className="gold-element-card new-element">
                  <div className="gold-element-row">
                    <strong>Add element</strong>
                    <span>or click a parser bbox to seed</span>
                  </div>
                  <label>
                    Stable id
                    <input
                      value={newElement.id}
                      onChange={(event) =>
                        setNewElement((value) => ({
                          ...value,
                          id: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Type
                    <select
                      value={newElement.type}
                      onChange={(event) =>
                        setNewElement((value) => ({
                          ...value,
                          type: event.target.value,
                        }))
                      }
                    >
                      {GOLD_TYPES.map((type) => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                  </label>
                  {newElement.type === 'heading' && (
                    <label>
                      Heading level
                      <input
                        type="number"
                        min="1"
                        max="6"
                        value={newElement.level}
                        onChange={(event) =>
                          setNewElement((value) => ({
                            ...value,
                            level: event.target.value,
                          }))
                        }
                      />
                    </label>
                  )}
                  <label>
                    Text
                    <textarea
                      value={newElement.text}
                      onChange={(event) =>
                        setNewElement((value) => ({
                          ...value,
                          text: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <button
                    type="button"
                    onClick={addElement}
                    disabled={busyAction === 'add-element'}
                  >
                    Add to staged draft
                  </button>
                </article>
              </section>

              {(session.page?.tasks || []).includes('reading_order') && (
                <section className="gold-editor-section">
                  <div className="gold-panel-title">
                    <strong>Reading order</strong>
                    <span>one element id per line</span>
                  </div>
                  <textarea
                    className="gold-reading-order"
                    value={readingOrderDraft}
                    onChange={(event) => setReadingOrderDraft(event.target.value)}
                  />
                  <button
                    type="button"
                    onClick={saveReadingOrder}
                    disabled={busyAction === 'reading-order'}
                  >
                    Save reading order
                  </button>
                </section>
              )}

              <section className="gold-editor-section gold-promotion">
                <div className="gold-panel-title">
                  <strong>Promotion preflight</strong>
                  <span className={preflight.ready ? 'ready' : 'blocked'}>
                    {preflight.ready ? 'READY' : 'BLOCKED'}
                  </span>
                </div>
                {!preflight.ready && (
                  <ul>
                    {(preflight.blockers || []).map((blocker) => (
                      <li key={blocker}>{blocker}</li>
                    ))}
                  </ul>
                )}
                <label>
                  Review note
                  <textarea
                    value={promotionNote}
                    onChange={(event) => setPromotionNote(event.target.value)}
                    placeholder="What was checked against the source page?"
                  />
                </label>
                <button
                  type="button"
                  className="gold-promote-button"
                  onClick={promote}
                  disabled={!preflight.ready || busyAction === 'promote'}
                >
                  Promote staged draft to reviewed artifact
                </button>

                {promoted && (
                  <div className="gold-promoted-artifact">
                    <strong>Reviewed artifact generated</strong>
                    <span>reviewed_by: {promoted.reviewed_by}</span>
                    <a href={api.getGoldReviewExportUrl(session.id)}>
                      Download reviewed gold JSON
                    </a>
                    <button
                      type="button"
                      onClick={publish}
                      disabled={Boolean(session.published_at) || busyAction === 'publish'}
                    >
                      {session.published_at
                        ? 'Published to canonical gold'
                        : 'Explicitly publish canonical gold'}
                    </button>
                    <small>
                      Publish performs an optimistic concurrency check against
                      the canonical annotation opened by this session.
                    </small>
                  </div>
                )}
              </section>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

export default GoldReviewWorkbench;
