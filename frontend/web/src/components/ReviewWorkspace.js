import React, { useEffect, useMemo, useState } from 'react';
import api from '../services/api';

function flattenNodes(nodes, depth = 0) {
  return nodes.flatMap((node) => [
    { ...node, depth },
    ...flattenNodes(node.children || [], depth + 1),
  ]);
}

function initialSelection(session) {
  const nodes = flattenNodes(session?.book?.nodes || []);
  const issue = session?.quality_report?.issues?.[0] || null;
  const node =
    issue?.node_ids
      ?.map((nodeId) => nodes.find((item) => item.id === nodeId))
      .find(Boolean) ||
    nodes[0] ||
    null;

  return {
    issueId: issue?.id || null,
    nodeId: node?.id || null,
    page: node?.source?.[0]?.page_index || 0,
  };
}

function ReviewWorkspace() {
  const [file, setFile] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [actionIssueId, setActionIssueId] = useState(null);
  const [aiActionId, setAiActionId] = useState(null);
  const [includeSourceImages, setIncludeSourceImages] = useState(false);
  const [error, setError] = useState(null);
  const [selectedIssueId, setSelectedIssueId] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [sourcePage, setSourcePage] = useState(0);

  const issues = session?.quality_report?.issues || [];
  const nodes = useMemo(
    () => flattenNodes(session?.book?.nodes || []),
    [session]
  );
  const decisions = useMemo(() => {
    const entries = (session?.decisions || []).map((decision) => [
      decision.issue_id,
      decision,
    ]);
    return new Map(entries);
  }, [session]);

  const aiProposals = session?.ai_proposals || [];
  const selectedAIProposals = aiProposals.filter(
    (proposal) => proposal.issue_id === selectedIssueId
  );
  const selectedIssue = issues.find((issue) => issue.id === selectedIssueId);
  const selectedNode = nodes.find((node) => node.id === selectedNodeId);
  const selectedIssueNode = selectedIssue?.node_ids
    ?.map((nodeId) => nodes.find((node) => node.id === nodeId))
    .find(Boolean);
  const focusedNode = selectedIssueNode || selectedNode;
  const focusedSource = focusedNode?.source?.[0] || null;

  useEffect(() => {
    const sessionId = localStorage.getItem('ebookAI-review-session');
    if (!sessionId) {
      return undefined;
    }

    let cancelled = false;
    api.getReviewSession(sessionId)
      .then((response) => {
        if (cancelled) {
          return;
        }
        const restored = response.data;
        const selection = initialSelection(restored);
        setSession(restored);
        setSelectedIssueId(selection.issueId);
        setSelectedNodeId(selection.nodeId);
        setSourcePage(selection.page);
      })
      .catch(() => {
        localStorage.removeItem('ebookAI-review-session');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const chooseIssue = (issue) => {
    setSelectedIssueId(issue.id);
    const node = issue.node_ids
      ?.map((nodeId) => nodes.find((item) => item.id === nodeId))
      .find(Boolean);
    if (node) {
      setSelectedNodeId(node.id);
      const source = node.source?.[0];
      if (source) {
        setSourcePage(source.page_index);
      }
    }
  };

  const chooseNode = (node) => {
    setSelectedNodeId(node.id);
    const source = node.source?.[0];
    if (source) {
      setSourcePage(source.page_index);
    }
  };

  const setNextSession = (nextSession) => {
    setSession(nextSession);
    localStorage.setItem('ebookAI-review-session', nextSession.id);
    const nextIssues = nextSession?.quality_report?.issues || [];
    const stillExists = nextIssues.some(
      (issue) => issue.id === selectedIssueId
    );
    if (!stillExists) {
      const first = nextIssues[0] || null;
      setSelectedIssueId(first?.id || null);
      const nextNodes = flattenNodes(nextSession?.book?.nodes || []);
      const node = first?.node_ids
        ?.map((nodeId) => nextNodes.find((item) => item.id === nodeId))
        .find(Boolean);
      setSelectedNodeId(node?.id || null);
      if (node?.source?.[0]) {
        setSourcePage(node.source[0].page_index);
      }
    }
  };

  const createSession = async () => {
    if (!file) {
      setError('Choose a PDF first.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await api.createReviewSession(file);
      const nextSession = response.data;
      const selection = initialSelection(nextSession);

      setSession(nextSession);
      localStorage.setItem('ebookAI-review-session', nextSession.id);
      setSelectedIssueId(selection.issueId);
      setSelectedNodeId(selection.nodeId);
      setSourcePage(selection.page);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to create review session.'
      );
    } finally {
      setLoading(false);
    }
  };

  const acceptIssue = async (issueId) => {
    setActionIssueId(issueId);
    setError(null);
    try {
      const response = await api.acceptReviewIssue(session.id, issueId);
      setNextSession(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to apply suggested patch.'
      );
    } finally {
      setActionIssueId(null);
    }
  };

  const rejectIssue = async (issueId) => {
    setActionIssueId(issueId);
    setError(null);
    try {
      const response = await api.rejectReviewIssue(session.id, issueId);
      setNextSession(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to reject issue.'
      );
    } finally {
      setActionIssueId(null);
    }
  };

  const generateAIProposal = async (issueId) => {
    setAiActionId(`generate:${issueId}`);
    setError(null);
    try {
      const response = await api.generateAIRepairProposal(
        session.id,
        issueId,
        null,
        includeSourceImages
      );
      setNextSession(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to generate a grounded AI proposal.'
      );
    } finally {
      setAiActionId(null);
    }
  };

  const acceptAIProposal = async (proposalId) => {
    setAiActionId(`accept:${proposalId}`);
    setError(null);
    try {
      const response = await api.acceptAIRepairProposal(
        session.id,
        proposalId
      );
      setNextSession(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to apply the AI proposal.'
      );
    } finally {
      setAiActionId(null);
    }
  };

  const rejectAIProposal = async (proposalId) => {
    setAiActionId(`reject:${proposalId}`);
    setError(null);
    try {
      const response = await api.rejectAIRepairProposal(
        session.id,
        proposalId
      );
      setNextSession(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to reject the AI proposal.'
      );
    } finally {
      setAiActionId(null);
    }
  };

  const counts = session?.quality_report?.counts || {};
  const score = session?.quality_report?.score;
  const orchestration = session?.orchestration || {};
  const attempts = orchestration.attempts || [];

  return (
    <div className="review-workspace">
      <section className="review-upload-card">
        <div>
          <h2>Human Review</h2>
          <p>
            Parse a PDF into BookIR, inspect source-grounded quality issues,
            review deterministic patches, and export the reviewed result.
          </p>
        </div>
        <div className="review-upload-controls">
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => {
              setFile(event.target.files?.[0] || null);
              setError(null);
            }}
          />
          <button
            className="review-primary-button"
            onClick={createSession}
            disabled={!file || loading}
          >
            {loading ? 'Analyzing…' : 'Create review session'}
          </button>
        </div>
        {file && <div className="review-file-name">Selected: {file.name}</div>}
      </section>

      {error && <div className="error-message">{error}</div>}

      {session && (
        <>
          <section className="review-summary">
            <div className="review-summary-main">
              <div>
                <span className="review-label">Document</span>
                <strong>{session.source_filename}</strong>
              </div>
              <div>
                <span className="review-label">Parser</span>
                <strong>{orchestration.selected_parser || 'unknown'}</strong>
              </div>
              <div>
                <span className="review-label">Quality</span>
                <strong>
                  {typeof score === 'number'
                    ? `${Math.round(score * 100)}%`
                    : 'n/a'}
                </strong>
              </div>
              <div>
                <span className="review-label">Route</span>
                <strong>
                  {orchestration.accepted ? 'Accepted' : 'Needs review'}
                </strong>
              </div>
            </div>

            <div className="review-summary-actions">
              <span className="review-count error">
                Errors {counts.error || 0}
              </span>
              <span className="review-count review">
                Review {counts.review || 0}
              </span>
              <span className="review-count info">
                Info {counts.info || 0}
              </span>
              <a
                className="review-export-link"
                href={api.getReviewExportUrl(session.id, 'bookir')}
              >
                Export BookIR
              </a>
              <a
                className="review-export-link"
                href={api.getReviewExportUrl(session.id, 'epub')}
              >
                Export EPUB
              </a>
            </div>
          </section>

          <section className="review-grid">
            <div className="review-panel source-panel">
              <div className="review-panel-header">
                <div>
                  <h3>Source PDF</h3>
                  <span>Page {sourcePage + 1}</span>
                </div>
                {focusedSource?.bbox && (
                  <code className="review-bbox">
                    bbox [
                    {focusedSource.bbox
                      .map((value) => value.toFixed(1))
                      .join(', ')}
                    ]
                  </code>
                )}
              </div>
              <iframe
                key={`${session.id}-${sourcePage}`}
                className="review-source-frame"
                src={`${api.getReviewSourceUrl(session.id)}#page=${sourcePage + 1}`}
                title="Source PDF"
              />
            </div>

            <div className="review-panel">
              <div className="review-panel-header">
                <div>
                  <h3>Reconstructed BookIR</h3>
                  <span>{nodes.length} nodes</span>
                </div>
              </div>
              <div className="review-node-list">
                {nodes.length === 0 && (
                  <div className="review-empty-state">
                    No BookIR nodes were produced. Check the issue queue for
                    parser escalation details.
                  </div>
                )}
                {nodes.map((node) => {
                  const source = node.source?.[0];
                  const related =
                    selectedIssue?.node_ids?.includes(node.id) || false;
                  return (
                    <button
                      key={node.id}
                      className={[
                        'review-node',
                        selectedNodeId === node.id ? 'selected' : '',
                        related ? 'related' : '',
                      ].join(' ')}
                      style={{ paddingLeft: `${14 + node.depth * 18}px` }}
                      onClick={() => chooseNode(node)}
                    >
                      <div className="review-node-meta">
                        <span className="review-node-type">{node.type}</span>
                        {source && <span>p.{source.page_index + 1}</span>}
                        <span>
                          S {Math.round((node.confidence?.structure || 0) * 100)}
                        </span>
                      </div>
                      <div className="review-node-content">
                        {node.content || '(empty node)'}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="review-panel">
              <div className="review-panel-header">
                <div>
                  <h3>Issue Queue</h3>
                  <span>{issues.length} current issues</span>
                </div>
              </div>
              <div className="review-issue-list">
                {issues.length === 0 && (
                  <div className="review-empty-state">
                    No current quality issues.
                  </div>
                )}
                {issues.map((issue) => {
                  const decision = decisions.get(issue.id);
                  const busy = actionIssueId === issue.id;
                  return (
                    <article
                      key={issue.id}
                      className={[
                        'review-issue',
                        selectedIssueId === issue.id ? 'selected' : '',
                        `severity-${issue.severity}`,
                      ].join(' ')}
                      onClick={() => chooseIssue(issue)}
                    >
                      <div className="review-issue-heading">
                        <span className="review-issue-code">{issue.code}</span>
                        <span className="review-severity">
                          {issue.severity}
                        </span>
                      </div>
                      <p>{issue.message}</p>
                      {decision && (
                        <div className="review-decision-badge">
                          Human decision: {decision.decision}
                        </div>
                      )}

                      {selectedIssueId === issue.id && (
                        <div className="review-issue-detail">
                          <div>
                            Nodes: {issue.node_ids?.join(', ') || 'book-level'}
                          </div>
                          {issue.evidence && (
                            <details>
                              <summary>Evidence</summary>
                              <pre>
                                {JSON.stringify(issue.evidence, null, 2)}
                              </pre>
                            </details>
                          )}
                          {issue.suggested_patch && (
                            <details>
                              <summary>Deterministic suggested patch</summary>
                              <pre>
                                {JSON.stringify(issue.suggested_patch, null, 2)}
                              </pre>
                            </details>
                          )}

                          <div className="review-ai-repair">
                            <div className="review-ai-repair-header">
                              <strong>Source-grounded AI proposals</strong>
                              <label className="review-ai-vision-toggle">
                                <input
                                  type="checkbox"
                                  checked={includeSourceImages}
                                  onChange={(event) => {
                                    event.stopPropagation();
                                    setIncludeSourceImages(event.target.checked);
                                  }}
                                  onClick={(event) => event.stopPropagation()}
                                />
                                Include source crop
                              </label>
                              <button
                                className="review-ai-generate-button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  generateAIProposal(issue.id);
                                }}
                                disabled={
                                  !issue.node_ids?.length ||
                                  aiActionId === `generate:${issue.id}`
                                }
                              >
                                {aiActionId === `generate:${issue.id}`
                                  ? 'Generating…'
                                  : 'Generate proposal'}
                              </button>
                            </div>

                            {!issue.node_ids?.length && (
                              <div className="review-ai-policy-note">
                                AI repair is disabled for book-level issues
                                without source-grounded target nodes.
                              </div>
                            )}

                            {selectedAIProposals.length === 0 &&
                              issue.node_ids?.length > 0 && (
                                <div className="review-ai-policy-note">
                                  No AI proposal yet. Generation is advisory
                                  only and never mutates BookIR. Enable source
                                  crop only for a vision-capable provider/model.
                                </div>
                              )}

                            {selectedAIProposals.map((proposal) => (
                              <div
                                key={proposal.id}
                                className={`review-ai-proposal ${proposal.status}`}
                              >
                                <div className="review-ai-proposal-meta">
                                  <span>
                                    {proposal.provider}/{proposal.model}
                                  </span>
                                  <span>{proposal.input_mode || 'text'}</span>
                                  <span>
                                    {Math.round(proposal.confidence * 100)}%
                                  </span>
                                  <strong>{proposal.status}</strong>
                                </div>
                                <p>{proposal.rationale}</p>
                                <div className="review-ai-evidence">
                                  Evidence nodes:{' '}
                                  {proposal.evidence_node_ids.join(', ')}
                                </div>
                                <div className="review-ai-evidence">
                                  Source ids:{' '}
                                  {proposal.evidence_source_ids.join(', ')}
                                </div>
                                {(proposal.source_image_refs || []).length > 0 && (
                                  <div className="review-ai-evidence">
                                    Source crops:{' '}
                                    {proposal.source_image_refs.length}
                                  </div>
                                )}
                                <details>
                                  <summary>AI patch</summary>
                                  <pre>
                                    {JSON.stringify(proposal.patch, null, 2)}
                                  </pre>
                                </details>
                                {proposal.status === 'pending' && (
                                  <div className="review-issue-actions">
                                    <button
                                      className="review-accept-button"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        acceptAIProposal(proposal.id);
                                      }}
                                      disabled={
                                        aiActionId ===
                                        `accept:${proposal.id}`
                                      }
                                    >
                                      {aiActionId ===
                                      `accept:${proposal.id}`
                                        ? 'Applying…'
                                        : 'Accept AI patch'}
                                    </button>
                                    <button
                                      className="review-reject-button"
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        rejectAIProposal(proposal.id);
                                      }}
                                      disabled={
                                        aiActionId ===
                                        `reject:${proposal.id}`
                                      }
                                    >
                                      Reject AI proposal
                                    </button>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>

                          <div className="review-issue-actions">
                            <button
                              className="review-accept-button"
                              onClick={(event) => {
                                event.stopPropagation();
                                acceptIssue(issue.id);
                              }}
                              disabled={!issue.suggested_patch || busy}
                            >
                              {busy ? 'Applying…' : 'Accept patch'}
                            </button>
                            <button
                              className="review-reject-button"
                              onClick={(event) => {
                                event.stopPropagation();
                                rejectIssue(issue.id);
                              }}
                              disabled={busy}
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>

              {(session.decisions || []).length > 0 && (
                <div className="review-decisions">
                  <h4>Reviewed decisions</h4>
                  {(session.decisions || []).map((decision) => (
                    <div
                      key={decision.issue_id}
                      className="review-decision-row"
                    >
                      <span>{decision.issue?.code || decision.issue_id}</span>
                      <strong>{decision.decision}</strong>
                    </div>
                  ))}
                </div>
              )}

              {aiProposals.length > 0 && (
                <div className="review-ai-history">
                  <h4>AI proposal history</h4>
                  {aiProposals.map((proposal) => (
                    <button
                      key={proposal.id}
                      className="review-ai-history-row"
                      onClick={() => {
                        const issue = issues.find(
                          (item) => item.id === proposal.issue_id
                        );
                        if (issue) {
                          chooseIssue(issue);
                        }
                      }}
                    >
                      <span>{proposal.issue?.code || proposal.issue_id}</span>
                      <span>{proposal.provider}/{proposal.model}</span>
                      <strong>{proposal.status}</strong>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="review-route-panel">
            <div className="review-panel-header">
              <div>
                <h3>Parser Orchestration Trail</h3>
                <span>
                  Stop reason: {orchestration.stop_reason || 'unknown'}
                </span>
              </div>
            </div>
            <div className="review-attempt-list">
              {attempts.length === 0 && (
                <div className="review-empty-state">
                  No parser attempts recorded.
                </div>
              )}
              {attempts.map((attempt, index) => (
                <div
                  key={`${attempt.parser_name}-${index}`}
                  className="review-attempt"
                >
                  <strong>{attempt.parser_name}</strong>
                  <span className={`attempt-status ${attempt.status}`}>
                    {attempt.status}
                  </span>
                  <span>score {attempt.quality_score ?? 'n/a'}</span>
                  <span>
                    requires{' '}
                    {(attempt.required_features || []).join(', ') || 'none'}
                  </span>
                  {attempt.reason && <span>{attempt.reason}</span>}
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default ReviewWorkspace;
