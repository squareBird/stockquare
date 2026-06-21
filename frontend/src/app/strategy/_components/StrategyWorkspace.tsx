'use client';

import { useState } from 'react';

import StrategyDetail from './StrategyDetail';
import StrategyForm from './StrategyForm';
import StrategyList from './StrategyList';

// Glue component that holds the selected strategy id and form-open state,
// then wires StrategyList, StrategyDetail, and StrategyForm together.
// Same shape as TradingWorkspace: no modals, inline right-pane content.
export default function StrategyWorkspace() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);

  function openCreate() {
    setEditId(null);
    setFormOpen(true);
  }

  function openEdit(id: number) {
    setEditId(id);
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setEditId(null);
  }

  return (
    <>
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div /> {/* spacer — h1 is in the page */}
        <button
          type="button"
          onClick={openCreate}
          className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90"
        >
          + 새 전략
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[320px_minmax(0,1fr)]">
        {/* Left rail */}
        <StrategyList
          selectedId={selectedId}
          onSelect={(id) => {
            setSelectedId(id);
            setFormOpen(false);
            setEditId(null);
          }}
          onEdit={openEdit}
        />

        {/* Right pane: form takes precedence over detail */}
        <div>
          {formOpen ? (
            <StrategyForm editId={editId} onClose={closeForm} />
          ) : selectedId !== null ? (
            <StrategyDetail
              strategyId={selectedId}
              onDeleted={() => setSelectedId(null)}
              onEdit={openEdit}
            />
          ) : (
            <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-gray-200 text-sm text-gray-400">
              전략을 선택하거나 새 전략을 만드세요.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
