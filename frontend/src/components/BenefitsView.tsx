import { useState } from "react";
import type { Benefit, BenefitPayload } from "../types/api";
import { formatBenefitConditions } from "../utils/formatters";
import { BenefitForm } from "./BenefitForm";

interface BenefitsViewProps {
  benefits: Benefit[];
  isLoading: boolean;
  error: string | null;
  isAdmin: boolean;
  isUserAuthenticated: boolean;
  onRetry: () => void;
  onCreateBenefit: (payload: BenefitPayload) => Promise<void>;
  onUpdateBenefit: (benefitId: number, payload: BenefitPayload) => Promise<void>;
  onDeleteBenefit: (benefitId: number) => Promise<void>;
}

export function BenefitsView({
  benefits,
  isLoading,
  error,
  isAdmin,
  isUserAuthenticated,
  onRetry,
  onCreateBenefit,
  onUpdateBenefit,
  onDeleteBenefit,
}: BenefitsViewProps) {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const canCreate = isAdmin || isUserAuthenticated;

  const canModifyBenefit = (benefit: Benefit): boolean => {
    const isGlobal = benefit.owner_id === null || benefit.owner_id === undefined;
    if (isAdmin) {
      return isGlobal;
    }
    return isUserAuthenticated && Boolean(benefit.is_own);
  };

  const handleDelete = async (benefitId: number) => {
    setActionError(null);
    setBusyId(benefitId);
    try {
      await onDeleteBenefit(benefitId);
      setConfirmDeleteId(null);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Nie udało się usunąć rabatu.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="benefits-view">
      <div className="stations-toolbar">
        <div>
          <h2 className="section-heading">Rabaty z aplikacji sieci</h2>
          <p className="station-meta">
            {canCreate
              ? isAdmin
                ? "Jako administrator zarządzasz globalnymi rabatami sieciowymi."
                : "Jako zalogowany kierowca możesz dodawać, edytować i usuwać własne rabaty."
              : "Zaloguj się w nagłówku (np. demo / demo), aby dodawać i zmieniać własne rabaty."}
          </p>
        </div>
        {canCreate && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowCreateForm((prev) => !prev)}
          >
            {showCreateForm ? "Zamknij formularz" : "+ Dodaj własny rabat"}
          </button>
        )}
      </div>

      {canCreate && showCreateForm && (
        <div className="form-wrapper">
          <BenefitForm
            onSave={async (payload) => {
              await onCreateBenefit(payload);
              setShowCreateForm(false);
            }}
            onCancel={() => setShowCreateForm(false)}
          />
        </div>
      )}

      {actionError && <p className="field-error">{actionError}</p>}

      {isLoading && benefits.length === 0 ? (
        <div className="state-box">Ładuję listę rabatów...</div>
      ) : error ? (
        <div className="state-box state-error">
          <p>Nie udało się pobrać rabatów: {error}</p>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
            Spróbuj ponownie
          </button>
        </div>
      ) : benefits.length === 0 ? (
        <div className="state-box">Brak skonfigurowanych rabatów. Dodaj pierwszą regułę.</div>
      ) : (
        <div className="benefits-list">
          {benefits.map((benefit) => {
            const canModify = canModifyBenefit(benefit);
            return canModify && editingId === benefit.id ? (
              <BenefitForm
                key={benefit.id}
                initialBenefit={benefit}
                onSave={async (payload) => {
                  await onUpdateBenefit(benefit.id, payload);
                  setEditingId(null);
                }}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <article key={benefit.id} className="card benefit-card">
                <div className="station-card-header">
                  <div>
                    <h3>
                      {benefit.app_name} <span className="rank-pill">{benefit.brand}</span>{" "}
                      {benefit.is_own ? (
                        <span className="benefit-scope-badge benefit-scope-own">Twój rabat</span>
                      ) : (
                        <span className="benefit-scope-badge">Globalny</span>
                      )}
                    </h3>
                    <p className="station-meta">
                      {formatBenefitConditions(benefit)} · Paliwo:{" "}
                      <strong>{benefit.fuel_type ?? "wszystkie"}</strong>
                    </p>
                    {benefit.description && <p className="benefit-desc">{benefit.description}</p>}
                    <p className="station-meta">
                      Ważny: {benefit.valid_from.slice(0, 10)} – {benefit.valid_to.slice(0, 10)} ·
                      Sprawdzono: {benefit.checked_at.slice(0, 10)}
                    </p>
                  </div>

                  {canModify && (
                    <div className="entity-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-xs"
                        onClick={() => setEditingId(benefit.id)}
                        disabled={busyId === benefit.id}
                      >
                        Edytuj
                      </button>
                      {confirmDeleteId !== benefit.id ? (
                        <button
                          type="button"
                          className="btn-vote btn-reject btn-xs"
                          onClick={() => setConfirmDeleteId(benefit.id)}
                          disabled={busyId === benefit.id}
                        >
                          Usuń
                        </button>
                      ) : (
                        <div className="confirm-delete-row">
                          <button
                            type="button"
                            className="btn-vote btn-reject btn-xs"
                            onClick={() => void handleDelete(benefit.id)}
                            disabled={busyId === benefit.id}
                          >
                            Potwierdź
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-xs"
                            onClick={() => setConfirmDeleteId(null)}
                            disabled={busyId === benefit.id}
                          >
                            Anuluj
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
