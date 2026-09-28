import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GoldReviewWorkbench from '../GoldReviewWorkbench';
import api from '../../services/api';

jest.mock('../../services/api', () => ({
  getGoldReviewQueue: jest.fn(),
  createGoldReviewSession: jest.fn(),
  getGoldReviewPageUrl: jest.fn(() => 'http://localhost/page.png'),
  setGoldReviewTasks: jest.fn(),
  upsertGoldReviewElement: jest.fn(),
  deleteGoldReviewElement: jest.fn(),
  setGoldReviewReadingOrder: jest.fn(),
  confirmGoldReviewItem: jest.fn(),
  promoteGoldReview: jest.fn(),
  publishGoldReview: jest.fn(),
  getGoldReviewExportUrl: jest.fn(() => 'http://localhost/promoted.json'),
  getGoldReviewAuditUrl: jest.fn(() => 'http://localhost/audit.json'),
  createGoldConsensus: jest.fn(),
  adjudicateGoldConsensus: jest.fn(),
  publishGoldConsensus: jest.fn(),
  getGoldConsensusExportUrl: jest.fn(() => 'http://localhost/consensus.json'),
  getGoldConsensusAuditUrl: jest.fn(() => 'http://localhost/consensus-audit.json'),
}));

const queue = {
  items: [
    {
      document_id: 'fixture-doc',
      title: 'Fixture document',
      language: 'en',
      page_index: 3,
      tasks: ['headings', 'reading_order'],
      annotation_status: 'draft',
      source_sha256: 'a'.repeat(64),
    },
  ],
};

function sessionFixture(ready = false) {
  return {
    id: 'session-1',
    document_id: 'fixture-doc',
    page_index: 3,
    backend: 'pymupdf',
    source_sha256: 'a'.repeat(64),
    page: {
      width: 600,
      height: 800,
      tasks: ['headings', 'reading_order'],
      elements: [
        {
          id: 'h1',
          type: 'heading',
          text: '1 Introduction',
          level: 1,
        },
      ],
      reading_order: ['h1'],
    },
    parser_nodes: [
      {
        id: 'node-1',
        type: 'text_block',
        text: '1 Introduction',
        bbox: [50, 60, 220, 90],
      },
    ],
    decisions: [],
    evaluation: {
      metrics: {
        annotation_status: 'draft',
      },
      evidence: {},
    },
    preflight: ready
      ? { ready: true, blockers: [], missing_elements: [], missing_tasks: [] }
      : {
          ready: false,
          blockers: ['unconfirmed elements: h1'],
          missing_elements: ['h1'],
          missing_tasks: ['headings', 'reading_order'],
        },
    promoted_annotation: null,
    published_at: '',
  };
}

describe('GoldReviewWorkbench', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.getGoldReviewQueue.mockResolvedValue({ data: queue });
    api.createGoldReviewSession.mockResolvedValue({
      data: sessionFixture(false),
    });
  });

  test('loads the review queue and opens a source-pinned target', async () => {
    render(<GoldReviewWorkbench />);

    expect(
      await screen.findByText('Fixture document')
    ).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();

    fireEvent.click(screen.getByText('PDF page 3'));

    await waitFor(() => {
      expect(api.createGoldReviewSession).toHaveBeenCalledWith(
        'fixture-doc',
        3,
        'pymupdf'
      );
    });
    expect(
      await screen.findByText('unconfirmed elements: h1')
    ).toBeInTheDocument();
    expect(screen.getByText(/aaaaaaaaaaaaaaaa/i)).toBeInTheDocument();
  });

  test('promotion remains blocked until preflight is ready', async () => {
    render(<GoldReviewWorkbench />);
    fireEvent.click(await screen.findByText('PDF page 3'));

    const promote = await screen.findByText(
      'Promote staged draft to reviewed artifact'
    );
    expect(promote).toBeDisabled();

    api.createGoldReviewSession.mockResolvedValueOnce({
      data: sessionFixture(true),
    });
    fireEvent.click(screen.getByText('PDF page 3'));

    await waitFor(() => {
      expect(
        screen.getByText('Promote staged draft to reviewed artifact')
      ).not.toBeDisabled();
    });
  });

  test('compares two promoted sessions and surfaces consensus state', async () => {
    api.createGoldConsensus.mockResolvedValue({
      data: {
        id: 'bundle-1',
        status: 'consensus',
        reviewer_a: 'alice',
        reviewer_b: 'bob',
        conflicts: [],
        unresolved_conflicts: [],
        consensus_annotation: {
          reviewed_by: 'alice + bob',
        },
      },
    });

    render(<GoldReviewWorkbench />);
    fireEvent.click(await screen.findByText('PDF page 3'));
    await screen.findByText('unconfirmed elements: h1');

    fireEvent.change(screen.getByLabelText('Reviewer A session'), {
      target: { value: 'session-a' },
    });
    fireEvent.change(screen.getByLabelText('Reviewer B session'), {
      target: { value: 'session-b' },
    });
    fireEvent.click(screen.getByText('Compare independent reviews'));

    await waitFor(() => {
      expect(api.createGoldConsensus).toHaveBeenCalledWith(
        'session-a',
        'session-b'
      );
    });
    expect(await screen.findByText('Status: consensus')).toBeInTheDocument();
    expect(screen.getByText('reviewed_by: alice + bob')).toBeInTheDocument();
  });

  test('confirming a task requires reviewer identity', async () => {
    render(<GoldReviewWorkbench />);
    fireEvent.click(await screen.findByText('PDF page 3'));

    await screen.findByText('unconfirmed elements: h1');
    const confirmButtons = screen.getAllByText('Confirm');
    fireEvent.click(confirmButtons[0]);

    expect(
      screen.getByText(
        'Enter reviewer identity before confirming review items.'
      )
    ).toBeInTheDocument();
    expect(api.confirmGoldReviewItem).not.toHaveBeenCalled();
  });
});
